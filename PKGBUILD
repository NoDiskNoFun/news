# Maintainer: Bill Sideris <bill88t@bredos.org>

pkgname=bredos-news
pkgver=1.2.14
pkgrel=1
pkgdesc='BredOS news and system information utility'
arch=(any)
url=https://github.com/BredOS/sys-report
license=('GPL3')

depends=('python' 'python-aiohttp' 'python-psutil')
optdepends=('pacman-contrib: Show updatable packages' 'yay: Check for updatable development packages')

source=('99-bredos-news.sh' 'bredos-news.py' 'cleanup-bredos-news.hook')
sha256sums=('5dfa12531be0c234337321fb1f77a2569390f400c63888b02b45f1acbbf9f7e3'
            '691e1b743e16bb764d1c31d952a251e4b79bd4b37e900ff23f9c4ddbc52042f5'
            'b1c84a9edb941bfcb5354d24371ad7565ed82e7cbc4ce81b180fadbff8a85390')

package() {
    mkdir -p "${pkgdir}/usr/bin" "${pkgdir}/etc/profile.d" "${pkgdir}/etc/pacman.d/hooks/cleanup-bredos-news.hook"
    install -Dm755 "${srcdir}/bredos-news.py" "${pkgdir}/usr/bin/bredos-news"
    install -Dm755 "${srcdir}/99-bredos-news.sh" "${pkgdir}/etc/profile.d/"
    install -Dm644 "${srcdir}/cleanup-bredos-news.hook" "${pkgdir}/usr/share/libalpm/hooks/cleanup-bredos-news.hook"
}
