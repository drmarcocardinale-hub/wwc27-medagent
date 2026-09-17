# Hugging Face Space (Docker SDK) / any container host
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .
EXPOSE 7860
# Hugging Face Spaces default port
ENV PORT=7860
CMD ["wwc27-medagent", "--http"]
