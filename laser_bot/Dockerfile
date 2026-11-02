FROM python:3.12-slim
WORKDIR /app
COPY laser_bot/requirements.txt laser_bot/requirements.txt
RUN pip install --no-cache-dir -r laser_bot/requirements.txt
COPY laser_bot laser_bot
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "laser_bot"]
