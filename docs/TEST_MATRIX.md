# Test matrix

| Runtime | Required checks |
| --- | --- |
| Python 3.10 | compile + full pytest |
| Python 3.11 | compile + full pytest |
| Python 3.12 | compile + full pytest |

Additional repository policy checks run on the CI host independently of the Python matrix.

The matrix is intentionally dependency-light: the project remains based primarily on the Python standard library and pytest for verification.
