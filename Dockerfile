# Runs on any container host. Hugging Face Spaces needs the app to listen on app_port
# (7860) and sets no PORT itself, so that is the default here; Cloud Run injects its own PORT
# and overrides it.
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .
EXPOSE 7860
# Hugging Face Spaces default port
ENV PORT=7860
CMD ["wwc27-medagent", "--http"]
