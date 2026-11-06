"""
generate_cert.py
Run this ONCE to create a self-signed SSL certificate.
No extra packages needed — uses Python's built-in ssl + subprocess.

Usage:
    python generate_cert.py

Creates two files in your project folder:
    cert.pem   — certificate
    key.pem    — private key
"""

import subprocess
import sys
import os

def generate():

    cert = "cert.pem"
    key  = "key.pem"

    if os.path.exists(cert) and os.path.exists(key):
        print("✅ cert.pem and key.pem already exist. Nothing to do.")
        return

    print("Generating self-signed SSL certificate...")

    # Try openssl command (available on Windows via Git Bash, or built into Python env)
    try:
        subprocess.run([
            "openssl", "req", "-x509",
            "-newkey", "rsa:2048",
            "-keyout", key,
            "-out",    cert,
            "-days",   "365",
            "-nodes",
            "-subj",   "/CN=localhost"
        ], check=True)
        print("✅ cert.pem and key.pem created successfully.")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback: use Python cryptography library
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
        import datetime

        print("Using Python cryptography library...")

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Generate certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])

        cert_obj = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(u"localhost"),
                    x509.IPAddress(__import__('ipaddress').IPv4Address('127.0.0.1')),
                ]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256(), default_backend())
        )

        # Write key
        with open(key, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        # Write cert
        with open(cert, "wb") as f:
            f.write(cert_obj.public_bytes(serialization.Encoding.PEM))

        print("✅ cert.pem and key.pem created successfully.")

    except ImportError:
        print("❌ Could not generate certificate.")
        print("   Run this command manually in your terminal:")
        print()
        print('   pip install cryptography')
        print('   python generate_cert.py')
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    generate()