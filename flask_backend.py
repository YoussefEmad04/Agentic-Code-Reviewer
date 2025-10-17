from flask import Flask, render_template, request, jsonify, Response
import asyncio
from src.config import config
from src.repo_analyzer import analyze_repository, build_markdown_report

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

@app.route('/')
def home():
    return render_template('index.html')
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/health_config', methods=['GET'])
def health_config():
    # Diagnostic info to verify runtime configuration (no secrets leaked)
    key = (config.openai_api_key or '')
    masked = (len(key) >= 6)
    provider = 'openrouter' if 'openrouter.ai' in (config.openai_base_url or '').lower() else 'openai-compatible'
    return jsonify({
        'status': 'ok',
        'provider': provider,
        'base_url': config.openai_base_url,
        'model': config.openai_model,
        'api_key_present': masked,
        'api_key_length': len(key)
    })

@app.route('/analyze', methods=['POST'])
def analyze_code():
    try:
        # Support JSON and form submissions
        code = None
        file_extension = 'py'
        if request.is_json:
            body = request.get_json(silent=True) or {}
            code = (body.get('code') or '').strip()
            file_extension = (body.get('file_extension') or 'py').strip() or 'py'
        else:
            code = (request.form.get('code', '') or '').strip()
            file_extension = (request.form.get('file_extension', 'py') or 'py').strip() or 'py'

        if not code:
            return jsonify({
                'status': 'error',
                'error': 'Please provide code to analyze'
            }), 400

        # Enforce backend-side size limit (in addition to agent ingest)
        max_bytes = config.max_file_size_mb * 1024 * 1024
        if len(code.encode('utf-8')) > max_bytes:
            return jsonify({
                'status': 'error',
                'error': f'Maximum allowed payload is {config.max_file_size_mb}MB'
            }), 413

        # Import your existing agent here
        from src.agent import CodeReviewAgent

        # Initialize the agent
        agent = CodeReviewAgent()

        # Run the analysis (bridge async -> sync)
        result = asyncio.run(agent.review_code(code, file_extension))

        # Return the analysis results
        if not isinstance(result, dict):
            result = {'status': 'success', 'feedback': str(result), 'analysis_results': {}}
        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'analysis_results': {}
        }), 500

@app.route('/analyze_repo', methods=['POST'])
def analyze_repo():
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'error': 'Expected JSON body'}), 400
        body = request.get_json(silent=True) or {}
        repo_url = (body.get('repo_url') or '').strip()
        include_extensions = body.get('include_extensions') or None
        max_files = body.get('max_files') or None

        if not repo_url:
            return jsonify({'status': 'error', 'error': 'repo_url is required'}), 400

        result = analyze_repository(repo_url, include_extensions=include_extensions, max_files=max_files)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/analyze_repo_report', methods=['POST'])
def analyze_repo_report():
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'error': 'Expected JSON body'}), 400
        body = request.get_json(silent=True) or {}
        repo_url = (body.get('repo_url') or '').strip()
        include_extensions = body.get('include_extensions') or None
        max_files = body.get('max_files') or None

        if not repo_url:
            return jsonify({'status': 'error', 'error': 'repo_url is required'}), 400

        analysis = analyze_repository(repo_url, include_extensions=include_extensions, max_files=max_files)
        md = build_markdown_report(analysis)
        filename = 'code_review_report.md'
        return Response(md, mimetype='text/markdown', headers={
            'Content-Disposition': f'attachment; filename={filename}'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
