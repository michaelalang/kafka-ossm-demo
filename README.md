# Kafka Cluster in OpenShift ServiceMesh DataPlane Secure and OutboundPolicy restricted

This demo Lab is show casing two scenarios, one for OpenShift and ServiceMesh the other for a kind k8s Cluster.
Depending on what you want to utilize you need to change the `overlays` directory in the cluster deployment accordingly.

configurations you might want to adjust to fit your environment:

* the dns Name you want to frontend and jaeger/grafana (kind k8s) to be access able
  - `frontend/gateway.yml`
  - `frontend/vs.yml`
  - `overlays/kind/grafana.yml` (kind k8s only)
  - `overlays/kind/jaeger.yml` (kind k8s only)
* the `gateway` for the frontend utilizes `SSL` so it's expected that istio has a default certificate for the domain
  you expose the service to
* the Registry repository paths to fetch your build images from need to be change in kustomize at `newName`
  - if you desire those images are available at `quay.io/rhn_support_milang/(producer|consumer|frontent)`
  - `producer/kustomization.yaml`
  - `consumer/kustomization.yaml`
  - `frontend/kustomization.yaml`

For OpenShift deployments you can utilize the default routes exposed by the OpenShift ServiceMesh Operator accordingly.

## building the application images on your own

if you want to utilize your own version of the application code, you can build your own images or adapt the code provided.
To build the default show-case execute following

```
for image in producer consumer frontend ; do 
    export REPOSITORYNAME=quay.io/username/kafka-demo/${image}:latest
    cd ${image} && podman build -f Dockerfile -t ${REPOSITORYNAME} && podman push ${REPOSITORYNAME} && cd -
done 
```

the `REPOSITORYNAME` references shall match those specified in the kustomziation files as `overrides` for `newName`

## deploy the strimzi ClusterOperator

```
oc -n kafka create -k overlays/openshift/
oc -n kafka wait --for condition=Ready pod -l name=strimzi-cluster-operator
```

to ensure, even the operator itself participates in the Mesh, we need to patch the deployment accordingly

```
oc -n kafka patch deploy/strimzi-cluster-operator -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"true"}}}}}'
```

## deploy the `pizza` Cluster

```
oc -n kafka create -f cluster/cluster.yml
oc -n kafka wait --for condition=Ready pod -l strimzi.io/cluster=pizza
```

depending on the speed of your Cluster, you might need to run the wait condition again until all instances of zookeeper and brokers are up

```
oc -n kafka get pods
NAME                                        READY   STATUS    RESTARTS      AGE
pizza-kafka-0                               2/2     Running   0             48s
pizza-kafka-1                               2/2     Running   0             48s
pizza-kafka-2                               2/2     Running   0             48s
pizza-zookeeper-0                           2/2     Running   0             5m30s
pizza-zookeeper-1                           2/2     Running   0             5m30s
pizza-zookeeper-2                           2/2     Running   0             5m30s
strimzi-cluster-operator-7c6f97ff8f-8zg4t   2/2     Running   0             99s
```

## deploy the pizza store, kitchen, waiters and frontend

```
for deploy in consumer producer frontend ; do 
    oc -n kafka create -k ${deploy}
done
```

## restrict your ServiceMesh to enforce mTLS and prevent outbound connections

**!!! NOTE !!!** 
if you share the cluster you deploy this to with _any_ other workload, ensure that you do not break any other workload.
Do not enforce this on a production cluster without considering and evaluating the side effects these setting have.

The deployment shipps with a namespace mTLS enforced policy so you do not need to restrict your complete cluster if you do not want.

### kind k8s Clusters

to enforce mTLS on your kind k8s Cluster inject a `PeerAuthentication` CR in the istio-system namespace as follows

```
kind: PeerAuthentication
apiVersion: security.istio.io/v1beta1
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
``` 

to restrict outbound connections you need to patch your istio configMap and add following in the spec

```
$ oc -n istio-system edit cm istio
apiVersion: v1
data:
  mesh: |-
    defaultConfig:
       ...
    outboundTrafficPolicy:
      mode: REGISTRY_ONLY
       ...
```

### OpenShift ServiceMesh Clusters

to enforce mTLS on your Openshift ServiceMesh Cluster inject a `PeerAuthentication` CR in the istio-system namespace or `click` the `Data Plane Security` switch in your ServiceMeshControlPlane

```
kind: PeerAuthentication
apiVersion: security.istio.io/v1beta1
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
```

to restrict outbound connections you need to patch your ServiceMeshControlPlane CR and add following in the spec

```
apiVersion: maistra.io/v2
kind: ServiceMeshControlPlane
metadata:
  name: basic
  namespace: istio-system
spec:
  security:
    dataPlane:
      mtls: true
    ...
  proxy:
    networking:
      trafficControl:
        inbound: {}
        outbound:
          excludedIPRanges: 	# Note, this is necessary in OCP and OSSM
            - 172.31.0.1/32
          policy: REGISTRY_ONLY
    ...
```


## accessing the frontend for a UI based visualization of the Kafka streams

depending on which name you have chosen, you can access the service under the url

```
oc -n kafka get virtualservice  pizza-frontend -o jsonpath='https://{.spec.hosts[0]}'
```

## accessing the logs on the various stages of the pizzeria factory 

the store[x] deployment mimic's orders coming in 

```
oc -n kafka logs --tail 3 deploy/store1 
INFO:root:Sending: {'location': 'store1', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODIzNn0.LofKYjUS5iiZ8uBfm8v9eGVwS6LaHPnfF_RX279jUBg', 'name': 'Antonio Morgan', 'address': ['8017 Charles Island', 'Raymondstad, ID 34518'], 'phone': '877.324.6658x1930', 'timestamp': '19:12:16', 'customerid': 557, 'state': 'Hawaii', 'drinks': [{'name': 'Margerita', 'count': 1}]}
INFO:root:Sending: {'location': 'store1', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODIzOH0.teu0e6zkLQ6wLfblOLXBxL3vRr_WFJJhmymI3mu7yGQ', 'name': 'Antonio Russo', 'address': ['2569 Nicole Harbors Suite 497', 'Lake Charlesside, MS 41424'], 'phone': '865.871.1139x831', 'timestamp': '19:12:18', 'customerid': 84151, 'state': 'Kentucky', 'pizza': [{'name': 'Marinara', 'topings': 'Egg'}, {'name': 'Pepperoni', 'topings': 'Cheese'}, {'name': 'Salami', 'topings': 'Double Cheese'}, {'name': 'Pepperoni', 'topings': 'Cheese'}]}
INFO:root:Sending: {'location': 'store1', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODIzOH0.teu0e6zkLQ6wLfblOLXBxL3vRr_WFJJhmymI3mu7yGQ', 'name': 'Antonio Russo', 'address': ['2569 Nicole Harbors Suite 497', 'Lake Charlesside, MS 41424'], 'phone': '865.871.1139x831', 'timestamp': '19:12:18', 'customerid': 84151, 'state': 'Kentucky', 'drinks': [{'name': 'Margerita', 'count': 1}]}

oc -n kafka logs --tail 3 deploy/store2
INFO:root:Sending: {'location': 'store2', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODI2MH0.eYvQ8nZdK31oH9ZGOGjeBXM2IwVDqnRv86DG_1_b5zo', 'name': 'Thomas Crawford', 'address': ['63072 Brian Drive', 'Tiffanyport, NY 57795'], 'phone': '(328)111-8418x46103', 'timestamp': '19:12:40', 'customerid': 43406, 'state': 'Connecticut', 'drinks': [{'name': 'Margerita', 'count': 1}]}
INFO:root:Sending: {'location': 'store2', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODI2NX0.MntIn01o0ftKhwfrhqSIpFHpsQdBCsPjubXQ3WKuqu0', 'name': 'Christopher Mercer', 'address': ['0313 Stout Trail', 'Thomasfort, CO 13548'], 'phone': '049.091.7419', 'timestamp': '19:12:45', 'customerid': 693636, 'state': 'South Dakota', 'pizza': [{'name': 'Marinara', 'topings': 'Cheese'}, {'name': 'Salami', 'topings': 'Ham'}]}
INFO:root:Sending: {'location': 'store2', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODI2NX0.MntIn01o0ftKhwfrhqSIpFHpsQdBCsPjubXQ3WKuqu0', 'name': 'Christopher Mercer', 'address': ['0313 Stout Trail', 'Thomasfort, CO 13548'], 'phone': '049.091.7419', 'timestamp': '19:12:45', 'customerid': 693636, 'state': 'South Dakota', 'drinks': [{'name': 'Beer', 'count': 3}]}

oc -n kafka logs --tail 3 deploy/store3
INFO:root:Sending: {'location': 'store3', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODI4MH0.2o5t_B_s_qJfRVvqK1hw0TYlIEVISTFFFY6HiEpvJ5E', 'name': 'William Ross', 'address': ['101 Chad Fort', 'East Anthony, MT 76114'], 'phone': '(532)284-9243x02100', 'timestamp': '19:13:00', 'customerid': 82, 'state': 'Oregon', 'drinks': [{'name': 'Pepsi', 'count': 3}]}
INFO:root:Sending: {'location': 'store3', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODI5MH0.kxDMll7YAWUm0cxTu5D9k9yEn4Dlo15nydtV-1kx5AU', 'name': 'Anita Whitaker', 'address': ['8807 Angela Greens', 'Michaelborough, ID 80290'], 'phone': '001-370-309-4371x45264', 'timestamp': '19:13:10', 'customerid': 65, 'state': 'Illinois', 'pizza': [{'name': 'Diavola', 'topings': 'Double Cheese'}, {'name': 'Mari & Monti', 'topings': 'Ham'}, {'name': 'Diavola', 'topings': 'Ham'}, {'name': 'Pepperoni', 'topings': 'Ham'}]}
INFO:root:Sending: {'location': 'store3', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODI5MH0.kxDMll7YAWUm0cxTu5D9k9yEn4Dlo15nydtV-1kx5AU', 'name': 'Anita Whitaker', 'address': ['8807 Angela Greens', 'Michaelborough, ID 80290'], 'phone': '001-370-309-4371x45264', 'timestamp': '19:13:10', 'customerid': 65, 'state': 'Illinois', 'drinks': [{'name': 'Beer', 'count': 3}]}


oc -n kafka logs --tail 3 deploy/store4
INFO:root:Sending: {'location': 'store4', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODI5N30.ugdxIFu-m_yxvRzArZwlYKQj8gO7FPVOo0SKPZpLmwg', 'name': 'Brittney Reyes', 'address': ['757 Patrick Crest Apt. 883', 'Port Zacharymouth, RI 26776'], 'phone': '(906)705-2989', 'timestamp': '19:13:17', 'customerid': 18872, 'state': 'Kentucky', 'drinks': [{'name': 'Margerita', 'count': 1}]}
INFO:root:Sending: {'location': 'store4', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODMwNn0.KWN5vczQ1ZsUubfWq6X85PMtKp_2D8UuH3Z8hj1y2tI', 'name': 'Eric Ramirez', 'address': ['2243 Kathleen Extensions Suite 252', 'Port Brendaport, MO 13284'], 'phone': '+1-584-000-7134x444', 'timestamp': '19:13:26', 'customerid': 7, 'state': 'Wyoming', 'pizza': []}
INFO:root:Sending: {'location': 'store4', 'psk': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODMwNn0.KWN5vczQ1ZsUubfWq6X85PMtKp_2D8UuH3Z8hj1y2tI', 'name': 'Eric Ramirez', 'address': ['2243 Kathleen Extensions Suite 252', 'Port Brendaport, MO 13284'], 'phone': '+1-584-000-7134x444', 'timestamp': '19:13:26', 'customerid': 7, 'state': 'Wyoming', 'drinks': [{'name': 'Beer', 'count': 3}]}
```

the kitchen[x] deployment mimic's work going on in the kitchen

```
oc -n kafka logs -f deploy/kitchen1
...
{
  "location": "store1",
  "psk": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODI2OH0.RQsuEDRqfUDsgf17jubkhmKTfoyNLyjq2QnzY4fEKMY",
  "name": "Jaclyn Jordan",
  "address": [
    "PSC 3231, Box 7482",
    "APO AP 20242"
  ],
  "phone": "+1-491-496-7509x452",
  "timestamp": "19:12:48",
  "customerid": 602,
  "state": "Arkansas",
  "pizza": [
    {
      "name": "Marinara",
      "topings": "Egg"
...
```

the waiter[x] deployments mimic's work related to drinks (of course)

```
oc -n kafka logs -f deploy/waiter1
{
  "location": "store1",
  "psk": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwaXp6YSIsImV4cCI6MTY4NjMzODQzN30.4LMvDFpbN8_fE7GPTGS_Xw_GOkLrxe-HEbN45FoBwNY",
  "name": "Mark Lewis MD",
  "address": [
    "2310 Christine Coves Apt. 872",
    "Colemanview, CO 78442"
  ],
  "phone": "(633)525-2179",
  "timestamp": "19:15:37",
  "customerid": 46809,
  "state": "Tennessee",
  "drinks": [
    {
      "name": "Margerita",
      "count": 3
    }
  ]
}
...
```

## visualizing the Workload and communications in Kiali

in Openshift ServiceMesh 2.3.3, Kiali does not show the connections as mTLS even though the configuration enforces it (Bug).

![enter image description here](pictures/Kafka-OSSM-kiali.gif)

## tracing kafka requests 

the code provided tries to show some tracing and indication where a particular task is taking long.
Open your browser towards the Jaeger UI to see more.

* tracing a waiter being busy
![enter image description here](pictures/tracing01.png)
   
* drilling down to an kafka rebalance error
![enter image description here](pictures/tracing02.png)                                                                                                     

* monitoring frequency of orders in store1
![enter image description here](pictures/tracing03.png)

* drilling down on orders in store1
![enter image description here](pictures/tracing04.png)

