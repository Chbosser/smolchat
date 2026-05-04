<h1 align="left">
  <img src="static/icons/logo-icon.svg" width="40" alt="smolChat logo">
  smolChat
</h1>

smolChat is a small AWS-hosted LLM chat app I built for my Cloud Computing assignment. The main idea was to deploy a basic chat service using two separate EC2 instances: one public-facing web/app server and one private model server running vLLM.

The project is not really about making a powerful chatbot, because it's quite slow and not very smart. It is more about learning about and implementing the architecture: nginx in front, FastAPI behind it, authentication before chat access, and a private vLLM server that the public internet cannot directly reach.

The model being used is:

```text
HuggingFaceTB/SmolLM2-135M-Instruct
```

It is intentionally small because the assignment uses free-tier style CPU EC2 instances.

---

## Logo
<img width="767" height="339" alt="image" src="https://github.com/user-attachments/assets/1ba3fdd5-8bfc-4ce6-81dc-0c20bd31e32b" />


## Screenshots

### Login / Landing Page


<img width="1096" height="783" alt="Screenshot 2026-05-01 163842" src="https://github.com/user-attachments/assets/61d0d32e-4e7e-4093-b0b8-16f672398b34" />


---

### Chat Page


<img width="1100" height="785" alt="Screenshot 2026-05-01 163901" src="https://github.com/user-attachments/assets/3f86da45-17f5-4d48-8887-5eab34dfb025" />
<img width="1709" height="873" alt="Screenshot 2026-05-03 235055" src="https://github.com/user-attachments/assets/aebdb4e5-8780-4241-b5b5-cc46ae3ec659" />


---


## Architecture

The app uses a two-instance AWS setup.

```text
User Browser
    |
    v
Public EC2 Web Instance
nginx on port 80
    |
    v
FastAPI on 127.0.0.1:8080
    |
    v
Private EC2 Model Instance
vLLM on port 8000
```

There are two EC2 instances:

1. **Web Instance**
   - Runs nginx
   - Runs FastAPI
   - Serves the login/register/chat pages
   - Stores users and chat history in SQLite
   - Publicly reachable through HTTP

2. **Model Instance**
   - Runs Docker
   - Runs the vLLM OpenAI-compatible server
   - Hosts `HuggingFaceTB/SmolLM2-135M-Instruct`
   - Only reachable from the web instance over the private VPC network

The vLLM server is not meant to be public. The public user only talks to nginx. FastAPI then calls vLLM using the model instance private IP address.

---

## Security Setup

The security boundary is probably the most important part of the project.

The public internet can reach:

```text
Web Instance port 80
```

The public internet should not be able to reach:

```text
FastAPI port 8080
vLLM port 8000
```

FastAPI runs locally behind nginx:

```bash
uvicorn app:app --host 127.0.0.1 --port 8080
```

nginx proxies public HTTP traffic to FastAPI:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
}
```

The model server security group only allows inbound traffic to vLLM from the web instance security group. This keeps the raw model endpoint off the public internet.

---

## Backend

The backend is built with:

- Python
- FastAPI
- SQLite
- Jinja2 templates
- OpenAI Python client
- Argon2 password hashing
- signed session cookies

The app supports:

- account registration
- password-based login
- logout
- protected chat route
- per-user chat history
- private calls from FastAPI to vLLM

Users cannot access the chat page unless they are logged in. If they are logged out and try to visit `/chat`, they get redirected back to the login page.

Passwords are not stored directly. They are hashed using Argon2 before being saved to SQLite.

SQLite tables:

```sql
users
messages
```

The `messages` table stores chat history by user ID so that each user only sees their own messages.

---

## Frontend

The frontend is intentionally simple, dark, and minimal. I was heavily inspired by the UI of MonkeyType and ChatGPT.

The UI uses:

- HTML templates with Jinja2
- CSS in `static/css/style.css`
- SVG icons in `static/icons`
- dark theme colors
- chat bubbles similar to ChatGPT
- a sidebar with user info/logout
- hover tooltips
- placeholder theme menu

The main colors are:

```text
Background: #1e1e1e
Sidebar: #191919
Text field: #191919
Muted text: #4d4d4d
White text: #ffffff
smolChat blue: #007ACC
Logo text: #D4D4D4
```

Fonts:

```text
Logo font: Lexend Deca
Default font: Roboto Mono
```

There is also a small paint icon button in the corner. Right now it opens a theme menu placeholder. I was hoping to implement some of the color themes that MonkeyType has.

---

## Running the Web App

On the web EC2 instance:

```bash
cd ~/llm-web
source venv/bin/activate
uvicorn app:app --host 127.0.0.1 --port 8080
```

Then nginx serves it publicly through:

```text
http://WEB_PUBLIC_IP
```

For my deployment, the public web instance was reachable at:

```text
http://98.92.207.27
```

---

## Running vLLM

On the model EC2 instance, vLLM runs inside Docker.

Example command:

```bash
sudo docker run --rm \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  --ipc=host \
  -e VLLM_API_KEY=secret123 \
  vllm/vllm-openai-cpu:latest-x86_64 \
  HuggingFaceTB/SmolLM2-135M-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key secret123 \
  --dtype float32 \
  --max-model-len 128 \
  --max-num-batched-tokens 128 \
  --gpu-memory-utilization 0.50
```

The model is small and CPU-only, so responses are not super fast. I had to tool with the gpu-memory-utilization so that the LLM would even start.

---


## Things I Learned

This project had a lot more little deployment issues than I expected. Some of the bigger problems were:

- Python version issues
- vLLM CPU setup problems
- memory limits on small EC2 instances
- Docker port conflicts
- keeping FastAPI local-only behind nginx
- making sure the model server was private
- getting session login working correctly
- making the frontend look decent without breaking the backend

The final version is not a production system, but it does show the core cloud setup: public web app, private model server, authenticated chat, and persistent user-specific chat history.

---

## Folder Structure

```text
llm-web/
├── app.py
├── app.db
├── templates/
│   ├── auth.html
│   └── chat.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── icons/
│       ├── account-icon.svg
│       ├── git-icon.svg
│       ├── info-icon.svg
│       ├── login-icon.svg
│       ├── logo-icon.svg
│       ├── paint-icon.svg
│       └── register-icon.svg
└── README.md
```

---

## Future Improvements

Some things I would add if I had more time:

- better error handling when vLLM is down
- real theme switching
- password reset
- better mobile layout
- longer model responses
- cleaner chat history controls

## Demo Video
Here is a short video that showcases the account creation,log-in, and chatting in SmolChat(feat. Halo 2 Trapped in Amber):

https://github.com/user-attachments/assets/dcc471fb-e31e-4aa7-8142-78a35205811e


