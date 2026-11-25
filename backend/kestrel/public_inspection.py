"""Read-only owner review fingerprints; never writes an approval or reads a key."""
import argparse
import json
from kestrel.deployment_settings import _external,_read_json,canonical,sha,release_hash,test_suite_hash,PUBLIC_HOSTS


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('config_file');args=parser.parse_args()
    value=_read_json(_external(args.config_file))
    print(json.dumps({'config_hash':sha(canonical(value)),'release_hash':release_hash(),'test_suite_hash':test_suite_hash(),'hosts':PUBLIC_HOSTS},indent=2))


if __name__=='__main__':main()
