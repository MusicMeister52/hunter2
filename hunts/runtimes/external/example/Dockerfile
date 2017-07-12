FROM python:3.6.1-alpine3.6

COPY requirements/frozen.txt /opt/example/requirements.txt
WORKDIR /opt/example

RUN pip install -r /opt/example/requirements.txt

COPY . .

RUN addgroup -g 500 -S example \
 && adduser -s /sbin/nologin -G example -S -D -H -u 500 example \
 && install -d -g example -o example /srv/example
USER example
VOLUME /srv/example

EXPOSE 8080
CMD ["python", "example.py"]
