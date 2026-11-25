"""Fictional employer domains for explicitly provisioned local demo identities."""
DOMAINS={'firm':'freshfields.example','halden':'halden.example','castlegate':'castlegate.example'}
NAMED={'KESTREL_CHRIS_EMAIL':'chris.madden@freshfields.example',
       'KESTREL_SUMEET_EMAIL':'sumeet.josh_external@freshfields.example',
       'KESTREL_RAMI_EMAIL':'rami.jaloudi@freshfields.example'}

def username(profile,index):return f"{profile['prefix']}{index:02}@{DOMAINS[profile['org']]}"
