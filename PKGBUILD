# Maintainer: Bill Sideris <bill88t@bredos.org>

pkgname=bredos-news
pkgver=1.10.1
pkgrel=1
pkgdesc='BredOS news and system information utility'
arch=('any')
url=https://github.com/BredOS/news
license=('GPL3')
install=news.install

groups=(bredos)
depends=('python' 'python-requests' 'python-psutil' 'python-pyinotify' 'smartmontools' 'mmc-utils-git')

optdepends=('pacman-contrib: Show updatable packages' 'yay: Check for updatable development packages')

source=('99-bredos-news.sh'
        'bredos-news.py'
        'bredos-news-update-watcher.py'
        'bredos-news-update.service')
sha256sums=('SKIP'
            'SKIP'
            'SKIP'
            'SKIP')

package() {
    mkdir -p "${pkgdir}/usr/bin" "${pkgdir}/etc/profile.d"
    install -Dm755 "${srcdir}/bredos-news.py" "${pkgdir}/usr/bin/bredos-news"
    install -Dm755 "${srcdir}/99-bredos-news.sh" "${pkgdir}/etc/profile.d/"
    install -Dm755 "${srcdir}/bredos-news-update-watcher.py" "${pkgdir}/usr/bin/bredos-news-update-watcher"
    install -Dm644 "${srcdir}/bredos-news-update.service" "${pkgdir}/usr/lib/systemd/system/bredos-news-update.service"
}
