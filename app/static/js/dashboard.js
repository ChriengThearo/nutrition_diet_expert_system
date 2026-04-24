// Dashboard JavaScript - Common functions for all dashboards

class DashboardManager {
    constructor() {
        this.init();
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    init() {
        console.log('Dashboard initialized');
        this.loadDashboardData();
        this.setupTooltips();
        this.setupNotifications();
        this.setupUserDashboardAnimations();
    }

    setupEventListeners() {
        // Global dashboard event listeners
        document.addEventListener('DOMContentLoaded', () => {
            this.setupNavigation();
            this.setupModals();
            this.setupForms();
        });

        // Handle window resize
        window.addEventListener('resize', this.handleResize.bind(this));
        
        // Handle online/offline status
        window.addEventListener('online', this.handleOnlineStatus.bind(this));
        window.addEventListener('offline', this.handleOfflineStatus.bind(this));
    }

    loadDashboardData() {
        // Load dashboard-specific data based on current route
        const currentPath = window.location.pathname;
        
        if (currentPath.includes('/admin')) {
            this.loadAdminData();
        } else if (currentPath.includes('/doctor')) {
            this.loadDoctorData();
        } else if (currentPath.includes('/user')) {
            this.loadUserData();
        }
    }

    loadAdminData() {
        // Fetch admin dashboard data
        fetch('/dashboard/admin/data')
            .then(response => response.json())
            .then(data => {
                this.updateAdminStats(data);
                this.updateActivityFeed(data.activities);
            })
            .catch(error => console.error('Error loading admin data:', error));
    }

    loadDoctorData() {
        // Fetch doctor dashboard data
        fetch('/dashboard/doctor/data')
            .then(response => response.json())
            .then(data => {
                this.updateDoctorStats(data);
                this.updateConsultationFeed(data.consultations);
            })
            .catch(error => console.error('Error loading doctor data:', error));
    }

    loadUserData() {
        // Fetch user dashboard data
        fetch('/dashboard/user/data')
            .then(response => response.json())
            .then(data => {
                this.updateUserStats(data);
                this.updateDiagnosisHistory(data.diagnoses);
            })
            .catch(error => console.error('Error loading user data:', error));
    }

    setupUserDashboardAnimations() {
        if (!this.isUserDashboard()) {
            return;
        }

        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const selectors = [
            '.role-hero',
            '.hero-meta-card',
            '.metric-card',
            '.profile-card',
            '.history-card',
            '.panel-card',
            '.empty-state',
            '.plan-history-table tbody tr'
        ];

        const elements = new Set();
        selectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => elements.add(el));
        });

        let index = 0;
        elements.forEach(el => {
            el.classList.add('js-reveal');
            el.style.setProperty('--reveal-delay', `${Math.min(index * 80, 480)}ms`);
            index += 1;
        });

        if (prefersReducedMotion) {
            elements.forEach(el => el.classList.add('is-revealed'));
            return;
        }

        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) {
                    return;
                }

                const target = entry.target;
                target.classList.add('is-revealed');
                this.animateCountsIn(target);
                observer.unobserve(target);
            });
        }, {
            threshold: 0.15,
            rootMargin: '0px 0px -10% 0px'
        });

        elements.forEach(el => observer.observe(el));
    }

    animateCountsIn(container) {
        const targets = container.matches('.metric-card')
            ? container.querySelectorAll('.metric-value')
            : container.querySelectorAll('.metric-value');

        targets.forEach(el => this.animateCountUp(el));
    }

    animateCountUp(element) {
        if (!element || element.dataset.counted === 'true') {
            return;
        }

        const rawText = element.textContent.trim();
        const match = rawText.match(/-?\d+(?:\.\d+)?/);
        if (!match) {
            return;
        }

        const targetValue = Number(match[0]);
        if (!Number.isFinite(targetValue)) {
            return;
        }

        const decimals = match[0].includes('.') ? match[0].split('.')[1].length : 0;
        const formatter = new Intl.NumberFormat(undefined, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });

        element.dataset.counted = 'true';

        const duration = 900;
        const startValue = 0;
        const startTime = performance.now();

        const tick = now => {
            const elapsed = Math.min((now - startTime) / duration, 1);
            const eased = 1 - Math.pow(1 - elapsed, 3);
            const currentValue = startValue + (targetValue - startValue) * eased;
            element.textContent = formatter.format(currentValue);

            if (elapsed < 1) {
                requestAnimationFrame(tick);
            } else {
                element.textContent = formatter.format(targetValue);
            }
        };

        requestAnimationFrame(tick);
    }

    isUserDashboard() {
        return Boolean(document.querySelector('.dashboard-shell.user-shell')) ||
            window.location.pathname.includes('/dashboard/user');
    }

    updateAdminStats(data) {
        // Update admin statistics
        this.updateStatCard('total_users', data.total_users);
        this.updateStatCard('total_doctors', data.total_doctors);
        this.updateStatCard('total_rules', data.total_rules);
    }

    updateDoctorStats(data) {
        // Update doctor statistics
        const totalUsers = data.total_users ?? data.total_patients;
        this.updateStatCard('total_users', totalUsers);
        this.updateStatCard('total_patients', totalUsers);
        this.updateStatCard('consultations_today', data.consultations_today);
        this.updateStatCard('pending_diagnoses', data.pending_diagnoses);
        this.updateStatCard('rules_authored', data.rules_authored);
    }

    updateUserStats(data) {
        // Update user statistics
        this.updateStatCard('user_bmi', data.user_bmi);
        this.updateStatCard('active_goals', data.active_goals);
        this.updateStatCard('total_diagnoses', data.total_diagnoses);
        this.updateStatCard('upcoming_appointments', data.upcoming_appointments);
    }

    updateStatCard(elementId, value) {
        const element = document.getElementById(elementId);
        if (element && value !== undefined) {
            element.textContent = value;
            element.classList.add('updated');
            setTimeout(() => element.classList.remove('updated'), 1000);
        }
    }

    updateActivityFeed(activities) {
        const feedContainer = document.getElementById('activityFeed');
        if (feedContainer && activities) {
            feedContainer.innerHTML = activities.map(activity => `
                <div class="activity-item">
                    <div class="activity-time">${this.formatTime(activity.timestamp)}</div>
                    <div class="activity-title">${activity.title}</div>
                    <div class="activity-description">${activity.description}</div>
                </div>
            `).join('');
        }
    }

    updateConsultationFeed(consultations) {
        const feedContainer = document.getElementById('consultationFeed');
        if (feedContainer && consultations) {
            feedContainer.innerHTML = consultations.map(consultation => `
                <div class="consultation-item">
                    <div class="consultation-time">${this.formatTime(consultation.timestamp)}</div>
                    <div class="consultation-title">Patient: ${consultation.patient_name}</div>
                    <div class="consultation-description">${consultation.reason}</div>
                </div>
            `).join('');
        }
    }

    updateDiagnosisHistory(diagnoses) {
        const historyContainer = document.getElementById('diagnosisHistory');
        if (historyContainer && diagnoses) {
            historyContainer.innerHTML = diagnoses.map(diagnosis => `
                <div class="diagnosis-item">
                    <div class="diagnosis-time">${this.formatTime(diagnosis.timestamp)}</div>
                    <div class="diagnosis-title">${diagnosis.condition}</div>
                    <div class="diagnosis-description">Confidence: ${diagnosis.confidence}%</div>
                </div>
            `).join('');
        }
    }

    setupNavigation() {
        // Setup navigation interactions
        const navLinks = document.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                // Add loading state
                link.classList.add('loading');
                setTimeout(() => link.classList.remove('loading'), 500);
            });
        });
    }

    setupModals() {
        // Setup modal interactions
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            modal.addEventListener('show.bs.modal', (e) => {
                // Load modal content dynamically if needed
                const modalId = modal.id;
                this.loadModalContent(modalId);
            });
        });
    }

    setupForms() {
        // Setup form validation and submission
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!form.checkValidity()) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                form.classList.add('was-validated');
            });
        });
    }

    setupTooltips() {
        // Initialize Bootstrap tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    setupNotifications() {
        // Setup notification system
        this.notificationContainer = document.createElement('div');
        this.notificationContainer.className = 'notification-container';
        document.body.appendChild(this.notificationContainer);
    }

    showNotification(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show notification`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        this.notificationContainer.appendChild(notification);
        
        // Auto-remove after duration
        setTimeout(() => {
            notification.remove();
        }, duration);
    }

    loadModalContent(modalId) {
        // Load dynamic content for modals
        const modalContentMap = {
            'diagnosisModal': '/dashboard/doctor/diagnosis/interface',
            'auditModal': '/dashboard/admin/audit-log',
            'bmiModal': '/dashboard/user/data'
        };

        if (modalContentMap[modalId]) {
            fetch(modalContentMap[modalId])
                .then(response => response.json())
                .then(data => {
                    // Update modal content based on data
                    console.log(`Loaded content for ${modalId}:`, data);
                })
                .catch(error => console.error(`Error loading modal content for ${modalId}:`, error));
        }
    }

    startAutoRefresh() {
        // Auto-refresh dashboard data every 30 seconds
        setInterval(() => {
            this.loadDashboardData();
        }, 30000);
    }

    handleResize() {
        // Handle responsive layout adjustments
        const width = window.innerWidth;
        if (width < 768) {
            // Mobile adjustments
            document.body.classList.add('mobile-view');
        } else {
            document.body.classList.remove('mobile-view');
        }
    }

    handleOnlineStatus() {
        this.showNotification('Connection restored', 'success');
        this.loadDashboardData();
    }

    handleOfflineStatus() {
        this.showNotification('Connection lost. Some features may be unavailable.', 'warning');
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) {
            return 'Just now';
        } else if (diff < 3600000) {
            return Math.floor(diff / 60000) + ' minutes ago';
        } else if (diff < 86400000) {
            return Math.floor(diff / 3600000) + ' hours ago';
        } else {
            return date.toLocaleDateString();
        }
    }

    // Utility functions
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // API helpers
    async apiCall(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            }
        };

        const finalOptions = { ...defaultOptions, ...options };

        try {
            const response = await fetch(url, finalOptions);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            this.showNotification('An error occurred. Please try again.', 'danger');
            throw error;
        }
    }

    getCSRFToken() {
        // Get CSRF token from meta tag or cookie
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        
        // Fallback to cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') {
                return decodeURIComponent(value);
            }
        }
        
        return '';
    }

    // Loading states
    showLoading(element) {
        element.classList.add('loading');
        element.disabled = true;
    }

    hideLoading(element) {
        element.classList.remove('loading');
        element.disabled = false;
    }

    // Data validation
    validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    validatePhone(phone) {
        const re = /^[\d\s\-\+\(\)]+$/;
        return re.test(phone) && phone.replace(/\D/g, '').length >= 10;
    }

    // Chart helpers (if using charts)
    createChart(elementId, type, data, options = {}) {
        const ctx = document.getElementById(elementId);
        if (ctx) {
            // This would integrate with Chart.js or similar
            console.log(`Creating ${type} chart for ${elementId}`, data);
        }
    }

    // Export functions
    exportToCSV(data, filename) {
        const csv = this.convertToCSV(data);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
    }

    convertToCSV(data) {
        if (!data || data.length === 0) return '';
        
        const headers = Object.keys(data[0]);
        const csvHeaders = headers.join(',');
        const csvRows = data.map(row => 
            headers.map(header => `"${row[header] || ''}"`).join(',')
        );
        
        return [csvHeaders, ...csvRows].join('\n');
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboardManager = new DashboardManager();
});

// Global functions for template integration
window.showNotification = function(message, type, duration) {
    if (window.dashboardManager) {
        window.dashboardManager.showNotification(message, type, duration);
    }
};

window.apiCall = function(url, options) {
    if (window.dashboardManager) {
        return window.dashboardManager.apiCall(url, options);
    }
};

window.showLoading = function(element) {
    if (window.dashboardManager) {
        window.dashboardManager.showLoading(element);
    }
};

window.hideLoading = function(element) {
    if (window.dashboardManager) {
        window.dashboardManager.hideLoading(element);
    }
};
