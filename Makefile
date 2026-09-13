# Verbes standards du projet (docs/os/09-plateforme.md §2).
.PHONY: help bootstrap check test fitness skills skills-check scaffold ci

MODULES := $(wildcard modules/*/)

help:
	@echo "bootstrap  Préparer l'environnement (racine + tous les modules)"
	@echo "check      Validations rapides de tous les modules"
	@echo "test       Tests de tous les modules"
	@echo "fitness    Fitness functions d'architecture (manifests + frontières)"
	@echo "skills     Générer les skills Claude Code depuis les playbooks"
	@echo "scaffold   Créer un module : make scaffold NAME=x OWNER=team-y CRIT=standard"
	@echo "ci         fitness + check + test"

bootstrap:
	@pip install -q -r platform/fitness/requirements.txt
	@for m in $(MODULES); do \
		[ -f $$m/Makefile ] && $(MAKE) -C $$m bootstrap || true; \
	done

check:
	@for m in $(MODULES); do \
		echo "=== check $$m"; $(MAKE) -C $$m check || exit 1; \
	done

test:
	@for m in $(MODULES); do \
		echo "=== test $$m"; $(MAKE) -C $$m test || exit 1; \
	done

fitness:
	@python3 platform/fitness/manifests.py .
	@python3 platform/fitness/boundaries.py .

skills:
	@python3 platform/sync_skills.py

skills-check:
	@python3 platform/sync_skills.py --check

scaffold:
	@./platform/scaffold/new-module.sh $(NAME) $(OWNER) $(CRIT)

ci: fitness skills-check check test
