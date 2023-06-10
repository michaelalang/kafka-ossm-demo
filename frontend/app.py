#!/usr/bin/env python

import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

from kafka import KafkaConsumer
import os
import json
from faker import Faker
from time import sleep
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.instrumentation.kafka import KafkaInstrumentor
jaeger_exporter = JaegerExporter(
                    collector_endpoint='http://%s:%s/api/traces' % (
                        os.environ.get('JAEGER_ALL_IN_ONE_INMEMORY_COLLECTOR_PORT_14268_TCP_ADDR'),
                        os.environ.get('JAEGER_ALL_IN_ONE_INMEMORY_COLLECTOR_PORT_14268_TCP_PORT'))
)

fake = Faker()

def instrument(*args, **kwargs):
    SRV_NAME = os.environ.get('SRV_NAME', os.environ.get('HOSTNAME'))
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: SRV_NAME}))
    simple_processor = SimpleSpanProcessor(jaeger_exporter)
    provider.add_span_processor(simple_processor)
    trace.set_tracer_provider(provider)
    KafkaInstrumentor().instrument()

from flask import Flask, render_template_string, Response, stream_with_context
import json2html
import time

app = Flask(__name__)

JOB = os.environ.get('JOB', '.*')

instrument()
@stream_with_context
def get_orders():
    try:
        while True:
            consumer = KafkaConsumer(bootstrap_servers=[os.environ.get('KAFKA_BOOTSTRAP')],
                                     value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                                     group_id=str(fake.uuid4()),
                                     enable_auto_commit=False)
            consumer.subscribe(pattern=JOB)
            for n, message in enumerate(consumer):
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span('work-received') as span:
                    consumer.commit()
                    yield json2html.json2html.convert(json=message.value, encode='utf8')
    except Exception as kaferr: 
        app.logger.error(f"Kafka processing Exception {kaferr}")
        sleep (2)

@app.route('/')
def index():
    return Response(get_orders())

if __name__ == '__main__':
    app.debug = True
    app.run(host=os.environ.get('LISTEN', '0.0.0.0'),
            port=int(os.environ.get('PORT', 8080)), threaded=True)

