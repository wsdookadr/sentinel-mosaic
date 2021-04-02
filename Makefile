
docs:
	asciidoctor README.adoc

notebook:
	jupyter notebook --browser=firefox sandbox.ipynb

package_upload:
	rm -rf dist/ build/ *.egg-info/
	python3 setup.py sdist bdist_wheel
	twine upload dist/*

