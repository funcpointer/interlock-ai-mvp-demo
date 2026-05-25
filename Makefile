PY := /Users/kc/venv-12/bin/python
FIXTURES := /Users/kc/Documents/Claude/Projects/interlock-ai-v2/fixtures/pdfs
AUTH := examples/aes_authority.yaml

.PHONY: test coverage eval-version eval-negative eval-cross eval-scanned eval-fast eval-kuzu eval-search eval-examples eval-full doctor

test:
	$(PY) -m pytest -q

coverage:
	$(PY) -m coverage run --source=interlock_mvp -m pytest -q
	$(PY) -m coverage report -m --skip-covered --fail-under=70

doctor:
	$(PY) -m interlock_mvp doctor

eval-version:
	$(PY) -m interlock_mvp review $(FIXTURES)/doc_a_60pct.pdf $(FIXTURES)/doc_b_90pct.pdf --mode version --out runs/checkpoint-version --authority-config $(AUTH) --no-cloud --no-kuzu --max-candidates 80
	$(PY) -m interlock_mvp check runs/checkpoint-version --eval eval/demo.yaml

eval-negative:
	$(PY) -m interlock_mvp review $(FIXTURES)/doc_a_60pct.pdf $(FIXTURES)/doc_a_60pct.pdf --mode version --out runs/checkpoint-negative --authority-config $(AUTH) --no-cloud --no-kuzu --max-candidates 80
	$(PY) -m interlock_mvp check runs/checkpoint-negative --eval eval/negative.yaml

eval-cross:
	$(PY) -m interlock_mvp review $(FIXTURES)/spec_xfmr_001.pdf $(FIXTURES)/doc_a_60pct.pdf --mode cross-doc --out runs/checkpoint-cross --authority-config $(AUTH) --doc-a-type specification --doc-b-type protection_study --no-cloud --no-kuzu --max-candidates 80
	$(PY) -m interlock_mvp check runs/checkpoint-cross --eval eval/cross_doc.yaml

eval-scanned:
	$(PY) -m interlock_mvp review $(FIXTURES)/doc_a_scanned.pdf $(FIXTURES)/doc_a_scanned.pdf --mode version --out runs/checkpoint-scanned --authority-config $(AUTH) --no-cloud --no-kuzu --max-candidates 20
	$(PY) -m interlock_mvp check runs/checkpoint-scanned --eval eval/scanned.yaml

eval-fast: test eval-version eval-negative eval-cross eval-scanned

eval-kuzu:
	$(PY) -m interlock_mvp review $(FIXTURES)/doc_a_60pct.pdf $(FIXTURES)/doc_b_90pct.pdf --mode version --out runs/checkpoint-kuzu --authority-config $(AUTH) --no-cloud --max-candidates 80

eval-search:
	$(PY) -m interlock_mvp search runs/checkpoint-version "transformer rating" --limit 8

eval-examples:
	$(PY) -m interlock_mvp review $(FIXTURES)/synth_equipment_spec_v2.pdf $(FIXTURES)/synth_equipment_spec_v3.pdf --mode version --out runs/example-synth-equipment-spec --authority-config $(AUTH) --no-cloud --no-kuzu --max-candidates 100
	$(PY) -m interlock_mvp check runs/example-synth-equipment-spec --eval eval/synth_reference_smoke.yaml
	$(PY) -m interlock_mvp review $(FIXTURES)/real_ieee_xfmr_spec_guide.pdf $(FIXTURES)/real_sel_xfmr_protection.pdf --mode cross-doc --out runs/example-real-xfmr-cross --authority-config $(AUTH) --doc-a-type specification --doc-b-type protection_study --no-cloud --no-kuzu --max-candidates 100
	$(PY) -m interlock_mvp check runs/example-real-xfmr-cross --eval eval/real_xfmr_smoke.yaml

eval-full: eval-fast eval-search eval-examples eval-kuzu
