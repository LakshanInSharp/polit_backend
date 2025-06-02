# Backend API

A FastAPI-based backend service that provides AI-powered query processing and PDF document handling capabilities.


## Prerequisites

- Python 3.10
- Pinecone account and API key
- (Optional) OpenAI API key if using OpenAI models /or Deepseek API

## Installation

1. Clone the repository:
```bash
git clone <your-repository-url>
cd <repository-name>
```

2. Create and activate a virtual environment:
```bash
install python 3.10 in local

py -3.10 -m venv venv
or
python3.10 -m venv venv
# On Windows
venv\Scripts\activate
# On Unix or MacOS
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r req.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
```
Edit the `.env` file with your actual configuration values.

## Configuration



## Running the Application

Start the FastAPI server:
```bash
python app.py
```

The API will be available at `http://localhost:7000`

## API Documentation

Once the server is running, you can access:
- Swagger UI documentation: `http://localhost:7000/docs`


## Development
dd any new environment variables to `.env.example`

### Testing
The application includes logging for debugging purposes. Check the `app.log` file for detailed logs.

## Security Considerations

- Never commit your `.env` file to version control
- Keep your API keys secure
- Use appropriate CORS settings in production
- Implement rate limiting for production use

