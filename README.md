# Project Name

## Setting Up the Project

To run this project, you need to generate your own **API keys** and set them up in a `.env` file.

### 1. Generate API Keys
To use the service, you need to generate your own API keys from **[TomTom](https://developer.tomtom.com/)** or the relevant API provider.

- Go to the [TomTom Developer Portal](https://developer.tomtom.com/) and create an account.
- After logging in, create a new application to generate your **API Key**.
- You will receive one or more API keys that are required for this project.

### 2. Create `.env` File

After obtaining your API keys, create a `.env` file in the root directory of the project (if not already provided) with the following structure:

```bash
TOMTOM_API_KEY="your_generated_api_key"
TOMTOM_API_KEY2="your_second_generated_api_key"
