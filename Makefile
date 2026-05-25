PY := /Users/kc/venv-12/bin/python
FIXTURES := /Users/kc/Documents/Claude/Projects/interlock-ai-v2/fixtures/pdfs
AUTH := examples/aes_authority.yaml

.PHONY: test eval-version eval-negative eval-cross eval-scanned eval-fast eval-kuzu eval-full doctor

test:
	$(PY) -m pytest -q

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

eval-full: eval-fast eval-kuzu
