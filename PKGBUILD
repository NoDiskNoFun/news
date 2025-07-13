# Maintainer: Bill Sideris <bill88t@bredos.org>

pkgname=bredos-news
pkgver=1.17.0
pkgrel=1
pkgdesc='BredOS news and system information utility'
arch=('any')
url=https://github.com/BredOS/news
license=('GPL3')
groups=(bredos)
depends=('python' 'python-requests' 'python-psutil' 'python-pyinotify' 'smartmontools' 'mmc-utils-git' 'pacman-contrib')
optdepends=('yay: Check for updatable development packages')
makedepends=('cython' 'gcc' 'python')

source=(
  'client.py'
  'server.py'
  '99-bredos-news.sh'
  'bredos-news-update.service'
  'bredos-news.1'
  'client-launcher.sh'
  'server-launcher.sh'
)

sha256sums=('2d1137b2bb39837fc27044d1b6cd96022a07461bbab3a60ce8496b2d71fe958e'
            '0bc2ffb48561ce103a1f6e9678e6d331029ffe1f14a33820eda224b0fce6c853'
            '5dfa12531be0c234337321fb1f77a2569390f400c63888b02b45f1acbbf9f7e3'
            'c63d70907e9a2b1b96c4d618440ad10612822a8f18de2853af0a9402a868ec26'
            '0c8f13369aeedc0b2738f296f9c35e950e6043f28169c958762739e105e6a10e'
            'caee1037cb370a8e0b0c9b83a6cc2e6eca78fed16783833060cc10d5915fd6e4'
            '73ec248f7f8f9a09dd82cbda77df9be8bd4f35b1d06c1cae82a4f784510a7c0e')

build() {
    cd "$srcdir"

    if [[ "$CARCH" == "aarch64" ]]; then
        echo "==> Cythonizing for aarch64.."
        cython --embed -3 client.py -o client.c
        cython --embed -3 server.py -o server.c
        echo "==> Building optimized aarch64 binaries.."
        gcc client.c -o client.bin -mtune=native \
            $(python3-config --cflags --ldflags --embed) -Os -s
        gcc server.c -o server.bin -mtune=native \
            $(python3-config --cflags --ldflags --embed) -Os -s
    else
        echo
        echo "###############################################################################"
        echo "###            WARNING: Non-aarch64 architecture detected: $CARCH           ###"
        echo "###         No optimized native binaries will be built or installed.        ###"
        echo "### The launcher scripts will run the Python interpreted versions instead.  ###"
        echo "###############################################################################"
        echo
        echo "Do not ship this build or I'll stab you."
        echo " - Bill88t"
        sleep 5
    fi
}

package() {
    install -d "$pkgdir/usr/bin"
    install -d "$pkgdir/usr/share/bredos-news"
    install -d "$pkgdir/usr/share/man/man1"
    install -d "$pkgdir/etc/profile.d"
    install -d "$pkgdir/usr/lib/systemd/system"

    # Always install launcher wrappers (these detect arch and fallback)
    install -m755 "$srcdir/client-launcher.sh" "$pkgdir/usr/bin/bredos-news"
    install -m755 "$srcdir/server-launcher.sh" "$pkgdir/usr/bin/bredos-news-server"

    # Install binaries only if they exist (built on aarch64)
    if [[ -f "$srcdir/server.bin" ]]; then
        install -m755 "$srcdir/server.bin" "$pkgdir/usr/share/bredos-news/server.bin"
    fi
    if [[ -f "$srcdir/client.bin" ]]; then
        install -m755 "$srcdir/client.bin" "$pkgdir/usr/share/bredos-news/client.bin"
    fi

    # Always install original python sources for fallback
    install -m644 "$srcdir/client.py" "$pkgdir/usr/share/bredos-news/client.py"
    install -m644 "$srcdir/server.py" "$pkgdir/usr/share/bredos-news/server.py"

    # Service and manpage
    install -m644 "$srcdir/bredos-news-update.service" "$pkgdir/usr/lib/systemd/system/bredos-news-update.service"
    install -m644 "$srcdir/bredos-news.1" "$pkgdir/usr/share/man/man1/bredos-news.1"

    # Profile script
    install -m755 "$srcdir/99-bredos-news.sh" "$pkgdir/etc/profile.d/99-bredos-news.sh"
}
