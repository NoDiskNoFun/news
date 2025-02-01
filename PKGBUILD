# Maintainer: Bill Sideris <bill88t@bredos.org>

pkgname=bredos-news
pkgver=1.2.0
pkgrel=1
pkgdesc='BredOS news and system information utillity'
arch=(any)
url=https://github.com/BredOS/sys-report
license=('GPL3')

depends=('python' 'python-aiohttp' 'python-psutil')
optdepends=('pacman-contrib: Show updatable packages' 'yay: Check for updatable development packages')

source=('99-bredos-news.sh' 'bredos-news')
sha256sums=('5dfa12531be0c234337321fb1f77a2569390f400c63888b02b45f1acbbf9f7e3'
            '22d8301feaa39970f400777fe23640b59a3220096d1cbf97b8618477053f7edc')

package() {
    mkdir -p "${pkgdir}/usr/bin" "${pkgdir}/etc/profile.d"
    install -Dm755 "${srcdir}/bredos-news" "${pkgdir}/usr/bin/"
    install -Dm755 "${srcdir}/99-bredos-news.sh" "${pkgdir}/etc/profile.d/"
}
