## TeX Live (current) for TikZ / tkz-euclide image compilation
# Debian's texlive is too old (2019) for current tkz-euclide/tkz-elements,
# so we install a current TeX Live from TUG's tlnet and add only what we need.
export TEXLIVE_INSTALL_PREFIX=/usr/local/texlive
cd /tmp
curl -L -o install-tl.tar.gz https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz
mkdir -p install-tl
tar -xzf install-tl.tar.gz -C install-tl --strip-components=1
# unattended install of just the infrastructure (no engines/packages yet)
sudo perl install-tl/install-tl --no-interaction --scheme=scheme-infraonly --repository https://mirror.ctan.org/systems/texlive/tlnet
# find the installed bin directory (its name includes the year + arch) and add to PATH
TL_BIN="$(echo /usr/local/texlive/*/bin/x86_64-linux)"
echo "export PATH=$TL_BIN:\$PATH" | sudo tee /etc/profile.d/texlive.sh
export PATH="$TL_BIN:$PATH"
# install exactly the packages we need (current versions from tlnet)
sudo "$TL_BIN/tlmgr" install \
    latex latex-bin latexmk \
    pgf pgfplots standalone \
    tkz-euclide tkz-elements \
    geometry xcolor amsmath \
    collection-latexrecommended
# symlink binaries onto the system PATH (required after tlmgr install)
sudo "$TL_BIN/tlmgr" path add
cd /workspaces/checkit

## Poppler (pdftoppm) for PDF -> PNG conversion of compiled TikZ
sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y poppler-utils

## sage stuff

# Conda should already be installed in the codespace.  We need to add the conda-forge channel

conda config --add channels conda-forge
conda config --set channel_priority strict

# We don't want conda to open the base environment always:
conda config --set auto_activate_base false

# Now create a conda environment for sage (called sage):
conda create --yes -n sage sage python=3.12

conda init

echo 'conda activate sage' >> ~/.bashrc

eval "$('conda' 'shell.bash' 'hook' 2> /dev/null)"
conda activate sage


## everything else

python -m pip install --upgrade pip
python -m pip install -e ./dashboard[dev]
cd viewer
npm install .
