from python:3.12-slim

# Install dependencies
RUN pip install flask requests

WORKDIR /app
COPY . /app

EXPOSE 8080

CMD ["python", "main.py"]