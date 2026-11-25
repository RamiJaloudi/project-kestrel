"""User-authorized, current-user-only project development CA and TLS leaf."""
from datetime import datetime,timedelta,timezone
from ipaddress import ip_address
from pathlib import Path
import os
import ssl
import subprocess
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID

HOSTS=['localhost','admin.localhost','firm.localhost','client.localhost','bank.localhost']

def protect(path):
    if os.name=='nt':
        identity=subprocess.check_output(['whoami'],text=True).strip()
        subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r',identity+':(F)'],check=True,capture_output=True)

def prepare(target,trust=True):
    target.mkdir(exist_ok=True,parents=True)
    ca_key_path,ca_path=target/'local-ca.key',target/'local-ca.pem'
    now=datetime.now(timezone.utc)
    if ca_path.exists()!=ca_key_path.exists():raise RuntimeError('Incomplete local CA; inspect manually before replacement')
    if not ca_path.exists():
        ca_key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Project Kestrel local development CA')])
        ca=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,encipher_only=False,decipher_only=False),critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False)
            .sign(ca_key,hashes.SHA256()))
        ca_key_path.write_bytes(ca_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        protect(ca_key_path);ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    ca_key=serialization.load_pem_private_key(ca_key_path.read_bytes(),password=None)
    ca=x509.load_pem_x509_certificate(ca_path.read_bytes())
    if ca.not_valid_after_utc<now+timedelta(days=8):raise RuntimeError('Local CA nearing expiry; explicit CA rotation required')
    key_path,cert_path=target/'local.key',target/'local.pem'
    renew=not key_path.exists() or not cert_path.exists()
    if not renew:
        previous=x509.load_pem_x509_certificate(cert_path.read_bytes())
        renew=previous.issuer!=ca.subject or previous.not_valid_after_utc<now+timedelta(days=7)
    if renew:
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Project Kestrel localhost')])
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(ca.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(min(now+timedelta(days=90),ca.not_valid_after_utc))
            .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in HOSTS]+[x509.IPAddress(ip_address('127.0.0.1'))]),critical=False)
            .sign(ca_key,hashes.SHA256()))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        protect(key_path);cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    protect(ca_key_path);protect(key_path)
    if trust and os.name=='nt':
        der=ca.public_bytes(serialization.Encoding.DER)
        if not any(blob==der for blob,encoding,purpose in ssl.enum_certificates('ROOT')):
            subprocess.run(['certutil.exe','-user','-addstore','Root',str(ca_path)],check=True,capture_output=True)
        print('Local TLS ready; project CA trusted for current Windows user only.')
    return ca

if __name__=='__main__':prepare(Path(__file__).resolve().parents[1]/'.runtime')
