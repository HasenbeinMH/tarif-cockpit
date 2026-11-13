# Integrationstests in Docker (Python 3.14, Linux). Aufruf: tools\test-ha.ps1 [min] [pytest-Argumente]
# "min" testet gegen die kleinste unterstützte HA-Version (requirements_test_min.txt).
$req = 'requirements_test.txt'
$rest = @($args)
if ($rest.Count -gt 0 -and $rest[0] -eq 'min') { $req = 'requirements_test_min.txt'; $rest = $rest[1..($rest.Count)] | Where-Object { $_ } }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pytestArgs = ($rest -join ' ')
if (-not ($rest | Where-Object { $_ -notlike '-*' })) { $pytestArgs = "tests $pytestArgs" }
docker run --rm -v "${root}:/repo" -v tarif-cockpit-pip:/root/.cache/pip -w /repo python:3.14-slim `
  sh -c "pip install -q --root-user-action=ignore --disable-pip-version-check -r $req && python -m pytest $pytestArgs"
exit $LASTEXITCODE
