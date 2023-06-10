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

def instrument(*args, **kwargs):
    SRV_NAME = os.environ.get('SRV_NAME', os.environ.get('HOSTNAME'))
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: SRV_NAME}))
    simple_processor = SimpleSpanProcessor(jaeger_exporter)
    provider.add_span_processor(simple_processor)
    trace.set_tracer_provider(provider)
    KafkaInstrumentor().instrument()

fake = Faker()

def workstep1(span):
    span.add_event('workstep1', attributes=dict(doing='work', step=1))
    sleep(fake.random_int(1,3))
    span.add_event('workstep1', attributes=dict(doing='finished', step=1))
    
def workstep2(span):
    span.add_event('workstep2', attributes=dict(doing='work', step=2))
    sleep(fake.random_int(3,5))
    span.add_event('workstep2', attributes=dict(doing='finished', step=2))

def workstep3(span):
    span.add_event('workstep3', attributes=dict(doing='work', step=3))
    sleep(fake.random_int(5,10))
    span.add_event('workstep3', attributes=dict(doing='finished', step=3))

if bool(os.environ.get('DEBUG', False)):
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

SPEED = int(os.environ.get('SPEED', 2))
JOB   = os.environ.get('JOB', '.*')

instrument()
while True:
    try:
        consumer = KafkaConsumer(bootstrap_servers=[os.environ.get('KAFKA_BOOTSTRAP')],
                                 value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                                 group_id=str(fake.uuid4()),
                                 enable_auto_commit=False)
        consumer.subscribe(pattern=JOB)
        for message in consumer:
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span('work-received') as span:
                print(json.dumps(message.value, indent=2))
                workstep1(span)
                workstep2(span)
                workstep3(span)
                consumer.commit()
    except: sleep (2)
