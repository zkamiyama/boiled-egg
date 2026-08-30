External audio is intentionally not bundled.

Suggested folders:
  tsm_subjective/  Roberts & Paliwal TSM dataset + subjective labels
  ebu_sqam/        EBU SQAM test material
  production/      your licensed speech/music/percussive/stereo corpus
  elastique_ref/   outputs rendered with a licensed zplane SDK/build
  comparison/      matched outputs from external baseline tools

Useful commands:
  python3 eval/inspect_corpus.py data/external
  python3 eval/run_external.py --corpus data/external
  python3 eval/make_blind_manifest.py data/external/comparison

Do not commit third-party audio unless its redistribution terms explicitly allow it.
