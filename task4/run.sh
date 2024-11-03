rm licm.log
cd ..
source venv.sh
cd task4
# cat ../benchmarks/mem/major-elm.bril | bril2json | python aliasing.py --debug | bril2txt > major-elm.bril
# cat input.bril | bril2json | python aliasing.py --debug | bril2txt > two-sum.bril
cat setup_input.bril | bril2json | python aliasing.py --debug | bril2txt > major-elm.bril
cat major-elm.bril | bril2json | brili > major-elm.out
cat major-elm.bril | bril2json | brili -p > major-elm.prof
cat setup_input.bril | bril2json | brili -p > baseline_major-elm.prof