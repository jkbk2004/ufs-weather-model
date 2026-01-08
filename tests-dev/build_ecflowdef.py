from xmlbuilder_ecflow import XMLBuilderEcflow
from test_loader import TestLoader
from manifest_loader import load_manifest

loader = TestLoader("tests-yamls/by_app", "app_manifest.yaml")
manifest = load_manifest("app_manifest.yaml")

builder = XMLBuilderEcflow(loader, manifest, platform="hera")
builder.build()
builder.write_def("ecflow.def")
