from flask import Flask, render_template, request, jsonify
import asyncio

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

@app.route('/')
def home():
    return render_template('index.html')
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/analyze', methods=['POST'])
def analyze_code():
    try:
        code = request.form.get('code', '')

        if not code or not code.strip():
            return jsonify({
                'status': 'error',
                'error': 'Please provide code to analyze'
            }), 400

        # Import your existing agent here
        from src.agent import CodeReviewAgent

        # Initialize the agent
        agent = CodeReviewAgent()

        # Run the analysis (bridge async -> sync)
        result = asyncio.run(agent.review_code(code, "py"))

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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
