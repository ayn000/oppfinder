#!/usr/bin/env python3
"""Account management CLI - the only way to create accounts (no public signup).

Usage:
    python manage.py create-user <username> [--name "Prénom"]
    python manage.py set-password <username>
    python manage.py delete-user <username>
    python manage.py list-users
"""
import argparse
import getpass
import sys

from app.auth import hash_password
from app.database import SessionLocal, init_db
from app.models import User


def _prompt_password() -> str:
    password = getpass.getpass("Mot de passe : ")
    confirm = getpass.getpass("Confirmation : ")
    if password != confirm:
        sys.exit("Les mots de passe ne correspondent pas.")
    if len(password) < 8:
        sys.exit("Le mot de passe doit faire au moins 8 caractères.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestion des comptes OppFinder")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create-user", help="Créer un compte")
    p_create.add_argument("username")
    p_create.add_argument("--name", default="", help="Nom affiché")

    p_pass = sub.add_parser("set-password", help="Changer un mot de passe")
    p_pass.add_argument("username")

    p_del = sub.add_parser("delete-user", help="Supprimer un compte (et ses alertes)")
    p_del.add_argument("username")

    sub.add_parser("list-users", help="Lister les comptes")

    args = parser.parse_args()
    init_db()
    db = SessionLocal()
    try:
        if args.cmd == "create-user":
            username = args.username.strip().lower()
            if db.query(User).filter(User.username == username).count():
                sys.exit(f'Le compte "{username}" existe déjà.')
            password = _prompt_password()
            db.add(
                User(
                    username=username,
                    display_name=args.name or username.capitalize(),
                    password_hash=hash_password(password),
                )
            )
            db.commit()
            print(f'Compte "{username}" créé.')

        elif args.cmd == "set-password":
            user = db.query(User).filter(User.username == args.username.strip().lower()).one_or_none()
            if user is None:
                sys.exit("Compte introuvable.")
            user.password_hash = hash_password(_prompt_password())
            db.commit()
            print("Mot de passe mis à jour.")

        elif args.cmd == "delete-user":
            user = db.query(User).filter(User.username == args.username.strip().lower()).one_or_none()
            if user is None:
                sys.exit("Compte introuvable.")
            confirm = input(f'Supprimer "{user.username}" et toutes ses alertes ? (oui/non) ')
            if confirm.strip().lower() != "oui":
                sys.exit("Annulé.")
            db.delete(user)
            db.commit()
            print("Compte supprimé.")

        elif args.cmd == "list-users":
            users = db.query(User).order_by(User.created_at).all()
            if not users:
                print("Aucun compte. Crée-en un avec : python manage.py create-user <nom>")
            for u in users:
                print(f"- {u.username} ({u.display_name}) - créé le {u.created_at:%d/%m/%Y}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
