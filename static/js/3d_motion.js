(function () {
    document.querySelectorAll('.frost-card, .glass-login-card').forEach(function (card) {
        card.addEventListener('mousemove', function (e) {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const rotateY = ((x - centerX) / centerX) * 6;
            const rotateX = -((y - centerY) / centerY) * 6;
            card.style.transform = `perspective(1100px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateZ(6px)`;
        });
        card.addEventListener('mouseleave', function () {
            card.style.transform = 'perspective(1100px) rotateX(0deg) rotateY(0deg) translateZ(0px)';
        });
    });

    document.querySelectorAll('.side-nav a').forEach(function (link) {
        link.addEventListener('click', function (e) {
            if (link.href && !link.href.endsWith('#')) {
                const stage = document.querySelector('.main-glass-stage');
                if (stage) {
                    stage.style.transition = 'transform 0.28s ease, opacity 0.28s ease';
                    stage.style.transform = 'perspective(1200px) rotateY(10deg) scale(0.97)';
                    stage.style.opacity = '0.35';
                }
            }
        });
    });
})();
