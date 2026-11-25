"""Trusted local OAuth client provisioning. Secrets entered, never printed."""
import argparse
from getpass import getpass
from sqlalchemy import select
from kestrel.models import Account, ServiceClient
from kestrel.database import make_engine, factory, database_url
from kestrel.services.auth import HASHER, audit
from kestrel.api.integrations import SCOPES

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('action',choices=['create','revoke'])
parser.add_argument('client_name')
parser.add_argument('--account')
parser.add_argument('--scopes',nargs='+',choices=sorted(SCOPES))
args=parser.parse_args()
with factory(make_engine(database_url()))() as db:
    client=db.scalar(select(ServiceClient).where(ServiceClient.client_name==args.client_name))
    if args.action=='revoke':
        if not client: parser.error('Unknown client')
        client.active=False
    else:
        if client: parser.error('Client already exists')
        account=db.scalar(select(Account).where(Account.username==args.account))
        if not account or not args.scopes: parser.error('Existing scoped account and scopes required')
        secret=getpass('Client secret (32+ characters): ')
        if len(secret)<32 or secret!=getpass('Confirm client secret: '): parser.error('Secret invalid')
        client=ServiceClient(client_name=args.client_name,account_id=account.id,scopes=' '.join(args.scopes),secret_hash=HASHER.hash(secret))
        db.add(client)
    audit(db,'oauth.client.'+args.action,'allowed',client.account_id)
    db.commit()
print('OAuth client configuration saved; no secret displayed.')
