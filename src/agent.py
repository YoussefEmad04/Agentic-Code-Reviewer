"""
Code Review Agent implementation using LangGraph with parallel analysis nodes.
"""

import asyncio
import operator
from typing import Dict, List, Any, Optional, TypedDict
from typing_extensions import Annotated

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import config


class AnalysisResult(TypedDict):
    """Result of a code analysis."""
    issues: List[Dict[str, str]]
    summary: str
    passed: bool


class CodeReviewState(TypedDict):
    """State for the code review workflow."""
    code: str
    file_extension: str
    language: str
    # Merge analysis results from parallel nodes by dict union
    analysis_results: Annotated[Dict[str, AnalysisResult], operator.or_]
    feedback: str
    error: Optional[str]
    metadata: Dict[str, Any]


class CodeReviewAgent:
    """AI-powered code review agent using LangGraph for workflow orchestration."""
    
    def __init__(self):
        """Initialize the code review agent with LLM and workflow."""
        self.llm = ChatOpenAI(
            model=config.openai_model,
            api_key=config.openai_api_key,
            temperature=0.2,
            base_url=config.openai_base_url
        )
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> Any:
        """Build the LangGraph workflow for code review.
        To avoid fan-in merge conflicts, we run analyses in parallel inside a single node.
        """
        workflow = StateGraph(CodeReviewState)

        # Nodes
        workflow.add_node("ingest_code", self._ingest_code)
        workflow.add_node("run_analyses", self._run_analyses)
        workflow.add_node("synthesize_feedback", self._synthesize_feedback)
        workflow.add_node("handle_error", self._handle_error)

        # Edges
        # Route based on ingest result: if error is set, go to handle_error; else proceed
        def _route_from_ingest(state: CodeReviewState) -> str:
            return "error" if state.get("error") else "ok"

        workflow.add_conditional_edges(
            "ingest_code",
            _route_from_ingest,
            {
                "error": "handle_error",
                "ok": "run_analyses",
            },
        )

        workflow.add_edge("run_analyses", "synthesize_feedback")
        workflow.add_edge("handle_error", END)

        workflow.set_entry_point("ingest_code")
        workflow.set_finish_point("synthesize_feedback")

        return workflow.compile()
    
    async def _ingest_code(self, state: CodeReviewState) -> CodeReviewState:
        """Ingest and validate the input code."""
        if not state.get("code"):
            return {"error": "No code provided", **state}
            
        file_extension = state.get("file_extension", "py").lower()
        language = self._detect_language(file_extension)
        
        if not language:
            return {"error": f"Unsupported file type: {file_extension}", **state}
            
        # Check file size limit (1MB = 1,048,576 bytes)
        max_size_bytes = config.max_file_size_mb * 1024 * 1024
        if len(state["code"].encode('utf-8')) > max_size_bytes:
            return {
                "error": f"File size exceeds the maximum limit of {config.max_file_size_mb}MB",
                **state
            }
            
        # Return only the keys this node is setting
        return {
            "language": language,
            "analysis_results": {},
            "metadata": {
                "file_extension": file_extension,
                "code_length": len(state["code"]),
                "file_size_mb": len(state["code"].encode('utf-8')) / (1024 * 1024)
            }
        }
    
    async def _security_analysis(self, state: CodeReviewState) -> CodeReviewState:
        """Analyze code for security vulnerabilities."""
        if not config.analyses["security"].enabled:
            return {}

        system_prompt = f"""
You are a security expert reviewing {state['language']} code. Provide a DETAILED security analysis.

For EACH security issue found:
1. Describe the vulnerability clearly
2. Explain the potential impact
3. Show the problematic code snippet
4. Provide a specific fix with code example

Focus on:
- Injection vulnerabilities (SQL, command, code injection)
- Authentication/Authorization issues
- Data exposure and sensitive information leaks
- Insecure dependencies or deprecated functions
- OWASP Top 10 vulnerabilities

If no issues found, state "No security vulnerabilities detected."

Provide detailed, actionable feedback with code examples.
        """
        
        return await self._analyze_code(state, "security", system_prompt)
    
    async def _maintainability_analysis(self, state: CodeReviewState) -> CodeReviewState:
        """Analyze code for maintainability issues."""
        if not config.analyses["maintainability"].enabled:
            return state
            
        system_prompt = f"""
You are a senior software engineer reviewing {state['language']} code. Provide a DETAILED maintainability analysis.

For EACH maintainability issue found:
1. Identify the code smell or anti-pattern
2. Explain why it's problematic
3. Show the problematic code
4. Suggest a better approach with code example

Focus on:
- Code smells (long methods, large classes, etc.)
- Anti-patterns and bad practices
- High complexity (cyclomatic/cognitive)
- SOLID principles violations
- Code duplication
- Poor error handling (bare except, swallowing exceptions)
- Unused variables and imports

If no issues found, state "Code maintainability is good."

Provide detailed, actionable feedback with code examples.
        """
        
        return await self._analyze_code(state, "maintainability", system_prompt)
    
    async def _style_analysis(self, state: CodeReviewState) -> CodeReviewState:
        """Analyze code for style and formatting issues."""
        if not config.analyses["style"].enabled:
            return state
            
        system_prompt = f"""
You are a code style expert reviewing {state['language']} code. Provide a DETAILED style analysis.

For EACH style issue found:
1. Point out the style violation
2. Explain the best practice
3. Show the problematic code
4. Provide a corrected version

Focus on:
- Naming conventions (variables, functions, classes)
- Code formatting (indentation, spacing, line length)
- Documentation and comments quality
- Consistent code style (quotes, imports organization)
- Language-specific best practices and idioms
- PEP 8 compliance (for Python)

If no issues found, state "Code style follows best practices."

Provide detailed, actionable feedback with code examples.
        """
        
        return await self._analyze_code(state, "style", system_prompt)
    
    async def _analyze_code(
        self,
        state: CodeReviewState,
        analysis_type: str,
        system_prompt: str
    ) -> CodeReviewState:
        """Generic method to run code analysis using LLM."""
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=state["code"])
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse the response into structured format
            result = self._parse_analysis_response(response.content, analysis_type)
            
            # Return only the delta for analysis_results to support parallel merge
            return {"analysis_results": {analysis_type: result}}
            
        except Exception as e:
            # Log error but don't fail the entire analysis
            error_result = AnalysisResult(
                issues=[{"error": str(e), "severity": "high"}],
                summary=f"{analysis_type} analysis failed",
                passed=False
            )
            
            return {"analysis_results": {analysis_type: error_result}}
    
    async def _run_analyses(self, state: CodeReviewState) -> CodeReviewState:
        """Run all analyses in parallel and combine their results."""
        tasks = []
        if config.analyses["security"].enabled:
            tasks.append(self._security_analysis(state))
        if config.analyses["maintainability"].enabled:
            tasks.append(self._maintainability_analysis(state))
        if config.analyses["style"].enabled:
            tasks.append(self._style_analysis(state))

        results = await asyncio.gather(*tasks) if tasks else []

        combined: Dict[str, AnalysisResult] = {}
        for part in results:
            for k, v in part.get("analysis_results", {}).items():
                combined[k] = v

        return {"analysis_results": combined}
    
    async def _synthesize_feedback(self, state: CodeReviewState) -> CodeReviewState:
        """Synthesize all analysis results into a cohesive review."""
        if not state.get("analysis_results"):
            return {**state, "feedback": "No analysis results to synthesize"}
            
        system_prompt = """
You are an expert senior software engineer conducting a comprehensive code review.

Synthesize the analysis results below into a DETAILED, well-organized code review.

Structure your review as follows:

## 🔴 Critical Issues (High Priority)
[List all high-severity issues with detailed explanations and fixes]

## 🟠 Important Issues (Medium Priority)
[List all medium-severity issues with detailed explanations and fixes]

## 🔵 Minor Issues (Low Priority)
[List all low-severity issues with suggestions]

## ✅ Positive Aspects
[Mention any good practices observed]

## 📋 Summary
[Provide an overall assessment and prioritized action items]

For each issue:
- Explain WHAT the problem is
- Explain WHY it's a problem
- Show the problematic code
- Provide a SPECIFIC fix with code example

Be detailed, constructive, and actionable. Use code blocks for examples.
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=str(state["analysis_results"]))
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            content = getattr(response, "content", "") or ""
            
            # Clean up LLM response (remove wrapper tags if present)
            content = self._clean_llm_response(content)
            
            # Debug: check if we got a response
            if not content or not content.strip():
                print(f"Warning: LLM returned empty content. Using fallback synthesis.")
                print(f"Analysis results: {state['analysis_results']}")
                content = self._fallback_synthesis(state["analysis_results"])
            else:
                print(f"Successfully synthesized feedback ({len(content)} chars)")
            
            return {
                "feedback": content,
                "status": "completed"
            }
        except Exception as e:
            print(f"Error in synthesize_feedback: {str(e)}")
            return {
                "feedback": self._fallback_synthesis(state["analysis_results"]),
                "status": "completed"
            }

    def _clean_llm_response(self, content: str) -> str:
        """Clean up LLM response by removing wrapper tags and fixing formatting."""
        if not content:
            return ""
        
        # Remove common wrapper tags
        content = content.replace("<s>", "").replace("</s>", "")
        content = content.replace("[OUT]", "").replace("[/OUT]", "")
        
        # Fix escaped backticks
        content = content.replace("` ``", "```")
        content = content.replace("`  ``", "```")
        
        return content.strip()
    
    def _fallback_synthesis(self, analysis_results: Dict[str, AnalysisResult]) -> str:
        """Create a detailed human-readable summary from analysis_results.
        Used when the LLM returns empty content.
        """
        if not analysis_results:
            return "## Code Review Summary\n\nNo analysis results available. Please ensure the code was analyzed properly."

        lines: List[str] = ["# 📋 Code Review Summary\n"]
        
        # Organize by category with proper formatting
        for category, result in analysis_results.items():
            lines.append(f"\n## {category.title()} Analysis\n")
            
            issues = result.get("issues", []) if isinstance(result, dict) else []
            if not issues:
                lines.append("✅ **No issues found in this category.**\n")
                continue
            
            for i, issue in enumerate(issues, 1):
                title = issue.get("title", f"{category.title()} Issue {i}")
                desc = issue.get("description") or issue.get("error") or "No description available"
                sev = issue.get("severity", "medium").upper()
                
                severity_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🔵"}.get(sev, "⚪")
                
                # Clean up the description (remove wrapper tags and fix backticks)
                desc = self._clean_llm_response(desc)
                
                lines.append(f"\n### {severity_icon} {title} [{sev}]\n")
                lines.append(f"{desc}\n")
                
                if "code" in issue:
                    lines.append(f"\n**Problematic code:**\n```python\n{issue['code']}\n```\n")
                
                if "suggestion" in issue:
                    lines.append(f"\n**Suggested fix:**\n```python\n{issue['suggestion']}\n```\n")
        
        return "\n".join(lines)
    
    async def _handle_error(self, state: CodeReviewState) -> CodeReviewState:
        """Handle errors in the workflow."""
        error_msg = state.get("error", "Unknown error occurred")
        return {
            "feedback": f"Error: {error_msg}",
            "status": "error"
        }
    
    def _detect_language(self, file_extension: str) -> Optional[str]:
        """Detect programming language from file extension."""
        language_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "java": "java",
            "go": "go"
        }
        return language_map.get(file_extension.lower())
    
    def _parse_analysis_response(
        self,
        response: str,
        analysis_type: str
    ) -> AnalysisResult:
        """Parse LLM response into structured format."""
        if not response or not response.strip():
            return AnalysisResult(
                issues=[],
                summary=f"No {analysis_type} issues detected",
                passed=True
            )
        
        # Parse the response into structured issues
        # For now, treat the entire response as a single detailed finding
        return AnalysisResult(
            issues=[{
                "title": f"{analysis_type.title()} Analysis",
                "description": response.strip(),
                "severity": "medium"
            }],
            summary=f"{analysis_type} analysis completed",
            passed=len(response.strip()) == 0
        )
    
    async def review_code(
        self,
        code: str,
        file_extension: str = "py"
    ) -> Dict[str, Any]:
        """
        Review the provided code and return the analysis.
        
        Args:
            code: The source code to review
            file_extension: The file extension (e.g., 'py', 'js')
            
        Returns:
            Dict containing the review results
        """
        initial_state = CodeReviewState(
            code=code,
            file_extension=file_extension,
            language="",
            analysis_results={},
            feedback="",
            error=None,
            metadata={}
        )
        
        try:
            result = await self.workflow.ainvoke(initial_state)
            return {
                "status": "success",
                **result
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
