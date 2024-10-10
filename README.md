
# Voice-Activated Trading System

This project is a voice based order placement system using Groq and OpenAI Whisper and OpenAlgo.


## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Overview

The **Voice-Activated Trading System** is a sophisticated platform that allows users to execute trading orders using voice commands. By leveraging speech recognition and natural language processing, users can seamlessly place buy or sell orders for various stocks and assets without manual input.

---

## Features

- **Voice Command Processing:** Record and process voice commands to execute trading orders.
- **Multiple Activation Commands:** Supports activation phrases like "MILO," "MYLO"
- **Exchange and Product Type Selection:** Users can select from various exchanges and product types before issuing commands.
- **Continuous Listening:** Automatically listens for commands and processes them without requiring repeated manual initiation.
- **Real-Time Feedback:** Displays transcription history, order statuses, and flash messages to inform users about order outcomes.
- **Error Handling:** Provides clear error messages in blue when orders fail due to invalid commands or other issues.

---



### Components

1. **Frontend (Client-Side)**
    - **Technologies:** HTML, JavaScript, Tailwind CSS
    - **Responsibilities:**
        - Capture audio from the user's microphone.
        - Detect silence to determine when to send audio data.
        - Allow users to select **Exchange** and **Product Type**.
        - Display transcription history and order statuses.
        - Provide user feedback through flash messages and status updates.

2. **Backend (Server-Side)**
    - **Technologies:** Python, Flask, Flask-CORS
    - **Responsibilities:**
        - Receive audio data and additional parameters from the frontend.
        - Transcribe audio using the **Groq API**.
        - Parse transcribed text to extract trading commands.
        - Place orders through the **OpenAlgo API**.
        - Send responses back to the frontend with transcription and order status.

3. **External Services**
    - **Groq API:** Transcribes audio recordings into text.
    - **OpenAlgo API:** Executes trading orders based on parsed commands.

4. **Environment Configuration**
    - **.env File:** Stores sensitive information like API keys and configuration settings.

---

## Technologies Used

- **Frontend:**
    - HTML5
    - JavaScript (ES6)
    - Tailwind CSS

- **Backend:**
    - Python 3.x
    - Flask
    - Flask-CORS
    - Requests
    - RatLimit
    - dotenv

- **APIs:**
    - Groq API for audio transcription
    - OpenAlgo API for placing trading orders

---

## Prerequisites

Before setting up the project, ensure you have the following installed on your system:

- **Python 3.7 or higher**
- **pip** (Python package installer)
- **Git** (for version control)

---

## Installation

1. **Clone the Repository**

    ```bash
    git clone https://github.com/marketcalls/openalgo-voice-based-orders.git
    cd openalgo-voice-based-orders
    ```

2. **Create a Virtual Environment**

    It's recommended to use a virtual environment to manage dependencies.

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install Backend Dependencies**

    ```bash
    pip install -r requirements.txt
    ```

    *Ensure that you have a `requirements.txt` file with all necessary Python packages.*

4. **Set Up the Frontend**

    The frontend uses standard HTML, JavaScript, and Tailwind CSS. No additional setup is required unless you plan to customize the frontend further.

---

## Configuration

1. **Create a `.env` File**

    In the root directory of the project, create a `.env` file to store environment variables.

    ```bash
    touch .env
    ```

2. **Populate the `.env` File**

    Open the `.env` file and add the following configurations:

    ```env
    GROQ_API_KEY=your_groq_api_key
    OPENALGO_API_KEY=your_openalgo_api_key
    OPENALGO_HOST=http://127.0.0.1:5000/
    VOICE_ACTIVATE_COMMAND=["MILO", "MYLO"]
    SECRET_KEY=your_flask_secret_key
    ```

    - **GROQ_API_KEY:** Your API key for the Groq transcription service.
    - **OPENALGO_API_KEY:** Your API key for the OpenAlgo trading service.
    - **OPENALGO_HOST:** The host URL for the OpenAlgo API.
    - **VOICE_ACTIVATE_COMMAND:** JSON array of supported activation commands.
    - **SECRET_KEY:** A secret key for Flask session management.

3. **Secure the `.env` File**

    Ensure that the `.env` file is **not** committed to version control by adding it to `.gitignore`.

    ```gitignore
    # .gitignore
    .env
    ```

---

## Usage

1. **Start the Flask Server**

    Ensure your virtual environment is activated and run:

    ```bash
    python app.py
    ```

    The server should start at `http://127.0.0.1:5001/`.

2. **Access the Application**

    Open your web browser and navigate to:

    ```
    http://127.0.0.1:5001/
    ```

3. **Using the System**

    - **Select Exchange and Product Type:**
        - Choose the desired **Exchange** and **Product Type** from the dropdown menus.
    
    - **Start Listening:**
        - Click the **"Start Listening"** button to begin issuing voice commands.
        - Grant microphone access when prompted.
    
    - **Issue Voice Commands:**
        - Speak your trading command clearly, for example:
            - "MILO buy 100  TCS."
            - "MYLO sell 50 Infosys."
            - "MILO buy 20 Zomato."
    
    - **Automatic Processing:**
        - After a brief pause (detected by silence), the system will process the command, place the order, and display the results.
    
    - **Stop Listening:**
        - Click the **"Stop Listening"** button to end the listening session.

4. **Viewing Transcription History and Order Status**

    - The **Transcription History** section displays all processed commands with timestamps.
    - Successful orders are indicated with green messages, while errors are shown in blue.

---

## API Endpoints

### 1. POST `/transcribe`

- **Description:** Receives audio data and user-selected parameters, transcribes the audio, parses trading commands, and places orders.

- **Parameters:**
    - **Form Data:**
        - `file`: Audio file (`audio.webm`, `audio/wav`, etc.)
        - `exchange`: Selected exchange (e.g., NSE, BSE)
        - `product_type`: Selected product type (e.g., CNC, NRML, MIS)

- **Response:**
    - **Success:**
        ```json
        {
            "task": "transcribe",
            "language": "English",
            "duration": 6.47,
            "text": "MILO buy 100 TCS.",
            "segments": [...],
            "order_response": {
                "orderid": "1234567890",
                "status": "success",
                ...
            }
        }
        ```
    - **Failure:**
        ```json
        {
            "error": "Invalid command"
        }
        ```

- **Status Codes:**
    - `200 OK`: Successful transcription and order placement.
    - `400 Bad Request`: Missing parameters or invalid data.
    - `500 Internal Server Error`: Unexpected server errors.

---

## Troubleshooting

1. **Orders Failing with "Invalid Command" Error**

    - **Cause:** Incorrect parsing of the trading symbol (e.g., "SHARES" instead of "TCS").
    - **Solution:** 
        - Ensure that the voice command follows the pattern: `<Activation Command> <Action> <Quantity> shares of <Symbol>.`
        - Example: "MILO buy 100 shares of TCS."

2. **Microphone Access Issues**

    - **Cause:** Browser permissions not granted or microphone not working.
    - **Solution:**
        - Ensure that the browser has permission to access the microphone.
        - Check if the microphone is properly connected and functioning.

3. **Transcription Errors**

    - **Cause:** Poor audio quality or unclear speech.
    - **Solution:**
        - Speak clearly and ensure minimal background noise.
        - Use a high-quality microphone for better audio capture.

4. **API Key Errors**

    - **Cause:** Incorrect or missing API keys in the `.env` file.
    - **Solution:**
        - Verify that all required API keys are correctly set in the `.env` file.
        - Ensure that there are no extra spaces or quotation marks around the keys.

5. **Server Not Starting**

    - **Cause:** Missing dependencies or incorrect Python version.
    - **Solution:**
        - Ensure that all dependencies are installed using `pip install -r requirements.txt`.
        - Verify that you're using Python 3.7 or higher.

---

## Security Considerations

1. **Protecting API Keys**

    - Store API keys securely in the `.env` file.
    - **Never** commit the `.env` file to version control.
    - Use environment variables or secret management tools in production environments.

2. **User Authentication (Recommended)**

    - Implement user authentication to ensure that only authorized users can place orders.
    - Use Flask extensions like [Flask-Login](https://flask-login.readthedocs.io/en/latest/) for managing user sessions.

3. **Secure Communication**

    - Use HTTPS to encrypt data transmission between the frontend and backend, especially since the application handles sensitive financial transactions.

4. **Input Validation**

    - Validate all inputs from the frontend to prevent injection attacks or malformed requests.

---

## Contributing

Contributions are welcome! If you'd like to enhance the system, please follow these steps:

1. **Fork the Repository**

2. **Create a New Branch**

    ```bash
    git checkout -b feature/YourFeatureName
    ```

3. **Make Changes and Commit**

    ```bash
    git commit -m "Add new feature"
    ```

4. **Push to Your Fork**

    ```bash
    git push origin feature/YourFeatureName
    ```

5. **Open a Pull Request**

    - Describe your changes and submit the pull request for review.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

- **Groq API:** For providing robust audio transcription services.
- **OpenAlgo API:** For facilitating seamless order placements in the trading system.
- **Tailwind CSS:** For enabling rapid and responsive frontend development.
- **Flask Community:** For the comprehensive backend framework and extensions.

---

*Disclaimer: This system is intended for educational purposes only. Ensure compliance with all relevant financial regulations and consult with a professional before engaging in actual trading activities.*
