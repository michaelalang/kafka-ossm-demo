#!/usr/bin/env python 
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

from kafka import KafkaProducer
from datetime import datetime
from json import dumps
from time import sleep
import os
from faker import Faker
import random
import jwt
from faker.providers import BaseProvider
import base64
from datetime import datetime, timedelta

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

def sign(psk, span):
    jwt_psk = base64.b64decode(psk)
    payload = {
        "iss": "pizza",
        "exp": datetime.utcnow() + timedelta(minutes=5),
    }
    return jwt.encode(payload, jwt_psk, algorithm='HS256')

if bool(os.environ.get('DEBUG', False)):
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

fake = Faker()
class PizzaProvider(BaseProvider):
    def pizza_name(self):
        validPizzaNames= ['Margherita',
                          'Marinara',
                          'Diavola',
                          'Mari & Monti',
                          'Salami',
                          'Pepperoni'
                        ]
        return validPizzaNames[random.randint(1,len(validPizzaNames)-1)]

class PizzaTopping(BaseProvider):
    def topping_name(self):
        validToppings = ['Corn',
                         'Cheese',
                         'Ham',
                         'Onions',
                         'Double Cheese',
                         'Egg',]
        return validToppings[random.randint(0, len(validToppings)-1)]

class Drinks(BaseProvider):
    def drink_name(self):
        validDrinks = ['Coca Cola',
                       'Beer',
                       'Margerita',
                       'Mai Tai',
                       'Negroni',
                       'Pepsi'
                      ]
        return validDrinks[random.randint(1,len(validDrinks)-1)]

fake.add_provider(PizzaProvider)
fake.add_provider(PizzaTopping)
fake.add_provider(Drinks)
branch = os.environ.get('BRANCH', fake.secondary_address())

psk = fake.uuid4()
logging.info(f"connecting to Workqueue {os.environ.get('KAFKA_BOOTSTRAP','localhost:9092')}")

instrument()
producer = KafkaProducer(bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP','localhost:9092'),
                         value_serializer=lambda x: dumps(x).encode('utf-8'))
while True:
    try:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span('work-received') as span:
            timestampStr = datetime.now().strftime("%H:%M:%S")
            span.add_event('customer', attributes=dict(doing='order', step=1, state='start'))
            orders = dict(location=branch,
                           psk=sign(psk, span),
                           name=fake.name(), address=fake.address().split('\n'),
                           phone=fake.phone_number(), timestamp=timestampStr,
                           customerid=fake.random_number(), state=fake.state(),
                           pizza=[{'name': fake.pizza_name(),
                                   'topings': fake.topping_name()} for _ in range(1, random.randint(0,5))])
            span.add_event('customer', attributes=dict(doing='order', step=2, state='finished'))
            span.add_event('customer', attributes=dict(doing='drinks', step=1, state='start'))
            drinks = dict(location=branch,
                           psk=sign(psk, span),
                           name=orders.get('name'), address=orders.get('address'),
                           phone=orders.get('phone'), timestamp=timestampStr,
                           customerid=orders.get('customerid'), state=orders.get('state'),
                           drinks=[{'name': fake.drink_name(),
                                    'count': fake.random_int(1,3)}])
            span.add_event('customer', attributes=dict(doing='drinks', step=2, state='finished'))
            logging.info(f"Sending: {orders}")
            producer.send(f"{branch}.orders", orders)
            logging.info(f"Sending: {drinks}")
            producer.send(f"{branch}.drinks", drinks)
            span.add_event('customer', attributes=dict(doing='finished', step=3))
            sleep(float(os.environ.get('SLEEP', fake.random_int(1,10))))
            span.add_event('customer', attributes=dict(doing='next', step=4))
    except: sleep(2)
