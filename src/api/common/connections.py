import requests
from voyages3 import localsettings

def fetch_connections_counts(node_class,ids):
	if not ids:
		return {}
	base_url=getattr(localsettings,'PEOPLE_NETWORKS_BASE_URL',None)
	if not base_url:
		return None
	try:
		r=requests.post(
			base_url.rstrip('/')+'/counts/',
			json={node_class:[int(i) for i in ids]},
			timeout=getattr(localsettings,'PEOPLE_NETWORKS_TIMEOUT',2)
		)
		r.raise_for_status()
		counts=r.json().get(node_class,{})
		return {int(k):int(v) for k,v in counts.items()}
	except Exception as e:
		print("connections counts unavailable:",e)
		return None

def connections_count_for(serializer,instance):
	counts=serializer.context.get('connections_counts')
	if counts is None:
		return None
	return counts.get(instance.id,0)
