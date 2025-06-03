Installation
============

Using UV (Recommended)
----------------------

.. code-block:: bash

   pip install uv
   git clone https://github.com/Whth/fabricatio.git
   cd fabricatio
   uvx --with-editable . maturin develop --uv -r
   # or with make
   make dev

Building Distribution
---------------------

.. code-block:: bash

   make bdist
