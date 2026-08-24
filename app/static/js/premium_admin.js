// Premium Admin Dashboard JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Update current date
    const dateElement = document.getElementById('admin-current-date');
    if (dateElement) {
        const today = new Date();
        const options = { month: 'short', day: 'numeric', year: 'numeric' };
        const formattedDate = today.toLocaleDateString('en-US', options);
        dateElement.innerHTML = `<i class="fas fa-calendar-alt"></i> ${formattedDate}`;
    }

    // Add smooth scroll behavior
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add ripple effect to action cards
    const actionCards = document.querySelectorAll('.admin-action-card, .nav-link-item, .stat-card');
    actionCards.forEach(card => {
        card.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = card.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple-effect');
            
            card.appendChild(ripple);
            
            setTimeout(() => ripple.remove(), 600);
        });
    });

    // Animate numbers on stat cards
    const animateValue = (element, start, end, duration) => {
        const range = end - start;
        const increment = range / (duration / 16);
        let current = start;
        
        const timer = setInterval(() => {
            current += increment;
            if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
                current = end;
                clearInterval(timer);
            }
            element.textContent = Math.floor(current).toLocaleString();
        }, 16);
    };

    // Observe stat cards and animate when in view
    const statNumbers = document.querySelectorAll('.stat-number');
    const observerOptions = {
        threshold: 0.5,
        rootMargin: '0px 0px -100px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.dataset.animated) {
                entry.target.dataset.animated = 'true';
                const finalValue = parseInt(entry.target.textContent.replace(/,/g, ''));
                entry.target.textContent = '0';
                animateValue(entry.target, 0, finalValue, 1000);
            }
        });
    }, observerOptions);

    statNumbers.forEach(num => observer.observe(num));

    // Add hover sound effect (optional - can be removed)
    const addHoverSound = (elements) => {
        elements.forEach(el => {
            el.addEventListener('mouseenter', () => {
                // Optional: Add subtle hover sound
                // const audio = new Audio('/static/sounds/hover.mp3');
                // audio.volume = 0.1;
                // audio.play();
            });
        });
    };

    // Notification bell animation
    const notificationBell = document.querySelector('.admin-notification');
    if (notificationBell) {
        setInterval(() => {
            const badge = notificationBell.querySelector('.badge');
            if (badge && parseInt(badge.textContent) > 0) {
                notificationBell.querySelector('i').style.animation = 'none';
                setTimeout(() => {
                    notificationBell.querySelector('i').style.animation = '';
                }, 10);
            }
        }, 30000); // Ring every 30 seconds if there are notifications
    }

    // Real-time clock for topbar
    const updateClock = () => {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
        });
        
        // Optional: Add a clock element if you want real-time updates
        const clockElement = document.getElementById('real-time-clock');
        if (clockElement) {
            clockElement.textContent = timeString;
        }
    };

    setInterval(updateClock, 1000);
    updateClock();

    // Add loading state management
    const addLoadingState = (button) => {
        button.addEventListener('click', function() {
            if (!this.classList.contains('loading')) {
                this.classList.add('loading');
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                
                // Simulate async operation
                setTimeout(() => {
                    this.classList.remove('loading');
                    this.innerHTML = originalText;
                }, 1500);
            }
        });
    };

    // Apply to all action cards
    document.querySelectorAll('.admin-action-card').forEach(addLoadingState);

    // Smooth fade-in on page load
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.5s ease-in-out';
        document.body.style.opacity = '1';
    }, 100);

    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl + K to focus search (if you add search later)
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('[type="search"]');
            if (searchInput) searchInput.focus();
        }
        
        // Escape to close modals/dropdowns
        if (e.key === 'Escape') {
            // Close any open modals or dropdowns
            document.querySelectorAll('.modal, .dropdown-menu').forEach(el => {
                el.classList.remove('show');
            });
        }
    });

    // Add performance monitoring (optional)
    if ('PerformanceObserver' in window) {
        const perfObserver = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                // Log slow operations
                if (entry.duration > 100) {
                    console.warn(`Slow operation detected: ${entry.name} took ${entry.duration}ms`);
                }
            }
        });
        
        perfObserver.observe({ entryTypes: ['measure'] });
    }

    console.log('%c🎨 Premium Admin Dashboard Loaded Successfully!', 
                'color: #4caf50; font-size: 16px; font-weight: bold;');
    console.log('%cVersion 2.0 - Enhanced Edition', 
                'color: #666; font-size: 12px;');
});

// Add CSS for ripple effect
const style = document.createElement('style');
style.textContent = `
    .ripple-effect {
        position: absolute;
        border-radius: 50%;
        background: rgba(76, 175, 80, 0.3);
        transform: scale(0);
        animation: ripple-animation 0.6s ease-out;
        pointer-events: none;
    }
    
    @keyframes ripple-animation {
        to {
            transform: scale(2);
            opacity: 0;
        }
    }
    
    .admin-action-card, .nav-link-item, .stat-card {
        position: relative;
        overflow: hidden;
    }
`;
document.head.appendChild(style);
