bind = "0.0.0.0:5000"
workers = 2
accesslog = "-"
errorlog = "-"
logger_class = "app.gunicorn_logging.GunicornJsonLogger"
