"""Generate an API_ADMIN_PASSWORD_HASH without printing the plaintext password."""

import getpass

from src.api.auth import hash_password


if __name__ == "__main__":
    print(hash_password(getpass.getpass("Password: ")))
