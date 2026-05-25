PY := /Users/kc/venv-12/bin/python
FIXTURES := /Users/kc/Documents/Claude/Projects/interlock-ai-v2/fixtures/pdfs
AUTH := examples/aes_authority.yaml
AES_MANIFEST ?= corpora/aes/local_manifest.yaml
AES_SEED_MANIFEST ?= corpora/aes/near_real_seed.yaml
PUBLIC_DEMO_MANIFEST ?= corpora/aes/public_demo_manifest.yaml

.PHONY: test coverage eval-version eval-negative eval-cross eval-scanned eval-fast eval-triage eval-kuzu eval-search eval-examples eval-public-demo eval-aes-corpus eval-aes-seed eval-full doctor

test:
	$(PY) -m pytest -q

coverage:
	$(PY) -m coverage run --source=interlock_mvp -m pytest -q
	$(PY) -m coverage report -m --skip-covered --fail-under=70

doctor:
	$(PY) -m interlock_mvp doctor

eval-version:
	$(PY) -m interlock_mvp review $(FIXTURES)/doc_a_60pct.pdf $(FIXTURES)/doc_b_90pct.pdf --mode version --out runs/checkpoint-version --authority-config $(AUTH) --no-cloud --no-kuzu
	$(PY) -m interlock_mvp check runs/checkpoint-version --eval eval/demo.yaml

eval-negative:
	$(PY) -m interlock_mvp review $(FIXTURES)/doc_a_60pct.pdf $(FIXTURES)/doc_a_60pct.pdf --mode version --out runs/checkpoint-negative --authority-config $(AUTH) --no-cloud --no-kuzu
	$(PY) -m interlock_mvp check runs/checkpoint-negative --eval eval/negative.yaml

eval-cross:
	$(PY) -m interlock_mvp review $(FIXTURES)/spec_xfmr_001.pdf $(FIXTURES)/doc_a_60pct.pdf --mode cross-doc --out runs/checkpoint-cross --authority-config $(AUTH) --doc-a-type specification --doc-b-type protection_study --no-cloud --no-kuzu
	$(PY) -m interlock_mvp check runs/checkpoint-cross --eval eval/cross_doc.yaml

eval-scanned:
	$(PY) -m interlock_mvp review $(FIXTURES)/doc_a_scanned.pdf $(FIXTURES)/doc_a_scanned.pdf --mode version --out runs/checkpoint-scanned --authority-config $(AUTH) --no-cloud --no-kuzu
	$(PY) -m interlock_mvp check runs/checkpoint-scanned --eval eval/scanned.yaml

eval-fast: test eval-version eval-negative eval-cross eval-scanned

eval-triage: eval-fast
	$(PY) -m interlock_mvp triage runs/checkpoint-version
	$(PY) -m interlock_mvp triage runs/checkpoint-cross
	$(PY) -m interlock_mvp triage runs/checkpoint-scanned

eval-kuzu:
	$(PY) -m interlock_mvp review $(FIXTURES)/doc_a_60pct.pdf $(FIXTURES)/doc_b_90pct.pdf --mode version --out runs/checkpoint-kuzu --authority-config $(AUTH) --no-cloud

eval-search:
	$(PY) -m interlock_mvp search runs/checkpoint-version "transformer rating" --limit 8

eval-examples:
	$(PY) -m interlock_mvp review $(FIXTURES)/synth_equipment_spec_v2.pdf $(FIXTURES)/synth_equipment_spec_v3.pdf --mode version --out runs/example-synth-equipment-spec --authority-config $(AUTH) --no-cloud --no-kuzu
	$(PY) -m interlock_mvp check runs/example-synth-equipment-spec --eval eval/synth_reference_smoke.yaml
	$(PY) -m interlock_mvp review $(FIXTURES)/real_ieee_xfmr_spec_guide.pdf $(FIXTURES)/real_sel_xfmr_protection.pdf --mode cross-doc --out runs/example-real-xfmr-cross --authority-config $(AUTH) --doc-a-type specification --doc-b-type protection_study --no-cloud --no-kuzu
	$(PY) -m interlock_mvp check runs/example-real-xfmr-cross --eval eval/real_xfmr_smoke.yaml

eval-public-demo:
	$(PY) scripts/make_synthetic_transformer_revision.py
	$(PY) -m interlock_mvp corpus $(PUBLIC_DEMO_MANIFEST) --out-root runs/public-demo --authority-config $(AUTH) --no-cloud --no-kuzu
	$(PY) -m interlock_mvp triage runs/public-demo/public_transformer_spec_synthetic_revision

eval-aes-corpus:
	@if [ -f "$(AES_MANIFEST)" ]; then \
		$(PY) -m interlock_mvp corpus $(AES_MANIFEST) --out-root runs/aes-corpus --authority-config $(AUTH) --no-cloud --no-kuzu; \
	else \
		echo "No AES local manifest at $(AES_MANIFEST). Copy corpora/aes/manifest.example.yaml to corpora/aes/local_manifest.yaml."; \
	fi

eval-aes-seed:
	$(PY) -m interlock_mvp corpus $(AES_SEED_MANIFEST) --out-root runs/aes-seed --authority-config $(AUTH) --no-cloud --no-kuzu

eval-full: eval-triage eval-search eval-examples eval-kuzu
