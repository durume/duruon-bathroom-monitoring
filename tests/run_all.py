
import unittest, sys, os
loader = unittest.TestLoader()
suite = loader.discover("tests")
runner = unittest.TextTestRunner(verbosity=2)
res = runner.run(suite)
sys.exit(0 if res.wasSuccessful() else 1)
