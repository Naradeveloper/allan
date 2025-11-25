// Mobile Navigation
document.addEventListener('DOMContentLoaded', function() {
    const mobileNavToggle = document.getElementById('mobileNavToggle');
    const mobileMenu = document.getElementById('mobileMenu');
    
    if (mobileNavToggle && mobileMenu) {
        mobileNavToggle.addEventListener('click', function() {
            this.classList.toggle('active');
            mobileMenu.classList.toggle('active');
            document.body.style.overflow = mobileMenu.classList.contains('active') ? 'hidden' : '';
        });
        
        // Close mobile menu when clicking on links
        const mobileLinks = mobileMenu.querySelectorAll('.mobile-nav-link');
        mobileLinks.forEach(link => {
            link.addEventListener('click', () => {
                mobileNavToggle.classList.remove('active');
                mobileMenu.classList.remove('active');
                document.body.style.overflow = '';
            });
        });
        
        // Close mobile menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!mobileNavToggle.contains(e.target) && !mobileMenu.contains(e.target)) {
                mobileNavToggle.classList.remove('active');
                mobileMenu.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    }
    
    // Close flash messages
    const alertCloseButtons = document.querySelectorAll('.alert-close');
    alertCloseButtons.forEach(button => {
        button.addEventListener('click', function() {
            this.closest('.alert').style.display = 'none';
        });
    });
    
    // Auto-hide flash messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.display = 'none';
        }, 5000);
    });
    
    // Filter products
    const filterButtons = document.querySelectorAll('.filter-btn');
    const productCards = document.querySelectorAll('.product-card');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filter = this.getAttribute('data-filter');
            
            // Update active button
            filterButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // Filter products
            productCards.forEach(card => {
                if (filter === 'all' || card.getAttribute('data-category') === filter) {
                    card.style.display = 'block';
                    setTimeout(() => {
                        card.style.opacity = '1';
                        card.style.transform = 'translateY(0)';
                    }, 50);
                } else {
                    card.style.opacity = '0';
                    card.style.transform = 'translateY(20px)';
                    setTimeout(() => {
                        card.style.display = 'none';
                    }, 300);
                }
            });
        });
    });
    
    // Add to cart functionality
    const addToCartButtons = document.querySelectorAll('.add-to-cart-btn');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', function() {
            const productId = this.getAttribute('data-product-id');
            window.location.href = `/add-to-cart/${productId}`;
        });
    });
    
    // Smooth scrolling for anchor links
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
    
    // Update cart count periodically
    function updateCartCount() {
        if (document.querySelector('.cart-link')) {
            fetch('/api/cart-count')
                .then(response => response.json())
                .then(data => {
                    const cartCounts = document.querySelectorAll('.cart-count');
                    cartCounts.forEach(count => {
                        count.textContent = data.count;
                    });
                })
                .catch(error => console.error('Error updating cart count:', error));
        }
    }
    
    // Update cart count every 30 seconds
    setInterval(updateCartCount, 30000);
    
    // Touch device improvements
    if ('ontouchstart' in window) {
        document.body.classList.add('touch-device');
    }
});

// Admin Panel functionality
document.addEventListener('DOMContentLoaded', function() {
    // Admin sidebar toggle
    const adminToggle = document.querySelector('.admin-toggle');
    const adminSidebar = document.querySelector('.admin-sidebar');
    const adminMain = document.querySelector('.admin-main');
    
    if (adminToggle && adminSidebar && adminMain) {
        adminToggle.addEventListener('click', function() {
            adminSidebar.classList.toggle('hidden');
            adminMain.classList.toggle('full-width');
        });
    }
    
    // Mobile admin menu
    const mobileAdminToggle = document.querySelector('.mobile-admin-toggle');
    if (mobileAdminToggle && adminSidebar) {
        mobileAdminToggle.addEventListener('click', function() {
            adminSidebar.classList.toggle('mobile-open');
        });
    }
    
    // Chart initialization (placeholder)
    const chartPlaceholders = document.querySelectorAll('.chart-placeholder');
    chartPlaceholders.forEach(chart => {
        chart.innerHTML = `
            <div style="text-align: center; color: var(--text-light);">
                <i class="fas fa-chart-bar" style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.5;"></i>
                <p>Sales analytics chart would be displayed here</p>
                <small>Integration with Chart.js or similar library</small>
            </div>
        `;
    });
});

// Utility functions
const utils = {
    formatCurrency: (amount) => {
        return new Intl.NumberFormat('en-KE', {
            style: 'currency',
            currency: 'KES'
        }).format(amount);
    },
    
    debounce: (func, wait) => {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    showNotification: (message, type = 'info') => {
        // Implementation for custom notifications
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
};

// Export for use in other scripts
window.appUtils = utils;