.PHONY: sync-skills validate-skills help

help:
	@echo "Available targets:"
	@echo "  sync-skills     - Sync skills from skills/ to .codex/skills/"
	@echo "  validate-skills - Validate skill format using skills-ref"

sync-skills:
	@echo "Syncing skills from skills/ to .codex/skills/..."
	@mkdir -p .codex/skills
	@rsync -av --delete skills/helm-gitops/ .codex/skills/helm-gitops/
	@echo "✓ Skills synced successfully"

validate-skills:
	@echo "Validating skill format..."
	@npx skills-ref validate skills/helm-gitops
	@npx skills-ref validate .codex/skills/helm-gitops
	@echo "✓ Skills validated successfully"
