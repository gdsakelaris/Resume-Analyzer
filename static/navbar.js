/**
 * Starscreen Navbar Component
 *
 * Shared navbar with subscription status, user menu, and global actions.
 * Works with Alpine.js for reactivity.
 *
 * Usage:
 * 1. Include this script in your HTML: <script src="/static/navbar.js"></script>
 * 2. Call renderNavbar() after DOM loads
 */

const API_BASE = '/api/v1';

// Subscription status Alpine.js component
function subscriptionStatus() {
    return {
        subscription: null,
        loading: false,

        async loadSubscription() {
            this.loading = true;
            try {
                const response = await Auth.fetch(`${API_BASE}/subscriptions/current`);
                if (response.ok) {
                    const data = await response.json();

                    // Add display name based on plan
                    const planDisplayNames = {
                        'free': 'Free',
                        'recruiter': 'Recruiter',
                        'small_business': 'Small Business',
                        'professional': 'Enterprise',
                        'enterprise': 'Enterprise'
                    };

                    this.subscription = {
                        ...data,
                        plan_display: data.plan_display || planDisplayNames[data.plan] || data.plan.toUpperCase()
                    };

                    console.log('Subscription loaded:', this.subscription);
                } else {
                    console.error('Failed to load subscription:', response.status);
                }
            } catch (error) {
                console.error('Error loading subscription:', error);
            } finally {
                this.loading = false;
            }
        },

        async cancelSubscription() {
            if (!this.subscription || this.subscription.plan === 'free') {
                return;
            }

            if (!confirm(`Are you sure you want to cancel your ${this.subscription.plan_display} subscription?\n\nYour subscription will remain active until the end of your billing period, then you'll be downgraded to the Free plan.`)) {
                return;
            }

            try {
                const response = await Auth.fetch(`${API_BASE}/subscriptions/cancel`, {
                    method: 'POST'
                });

                if (response.ok) {
                    alert('Subscription canceled successfully. You will be downgraded to the Free plan at the end of your billing period.');
                    window.location.reload();
                } else {
                    const errorData = await response.json();
                    alert('Failed to cancel subscription: ' + (errorData.detail || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error canceling subscription:', error);
                alert('Network error. Please try again.');
            }
        }
    };
}

// Global navbar actions
window.cancelSubscriptionGlobal = async function() {
    const user = Auth.getUser();
    if (!user) {
        alert('Please log in to manage your subscription.');
        return;
    }

    if (!confirm('Are you sure you want to cancel your subscription?\n\nYou will be downgraded to the Free plan at the end of your billing period.')) {
        return;
    }

    try {
        const response = await Auth.fetch(`${API_BASE}/subscriptions/cancel`, {
            method: 'POST'
        });

        if (response.ok) {
            alert('Subscription canceled successfully. You will be downgraded to the Free plan at the end of your billing period.');
            window.location.reload();
        } else {
            const errorData = await response.json();
            alert('Failed to cancel subscription: ' + (errorData.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error canceling subscription:', error);
        alert('Network error. Please try again.');
    }
};

window.deleteAccount = async function() {
    if (!confirm('⚠️ WARNING: This will permanently delete your account and all associated data.\n\nType "YES" in the next prompt to confirm.')) {
        return;
    }

    const confirmText = prompt('Type "YES" (in all caps) to confirm account deletion:');
    if (confirmText !== 'YES') {
        alert('Account deletion canceled. You must type "YES" exactly to confirm.');
        return;
    }

    try {
        const response = await Auth.fetch(`${API_BASE}/auth/me`, {
            method: 'DELETE'
        });

        if (response.ok) {
            alert('Your account has been permanently deleted.');
            Auth.logout();
        } else {
            const errorData = await response.json();
            alert('Failed to delete account: ' + (errorData.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting account:', error);
        alert('Network error. Please try again.');
    }
};

// Navbar HTML template
const navbarHTML = `
<nav class="bg-white border-b border-slate-200 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
            <a href="/" class="flex items-center gap-1 hover:opacity-80 transition cursor-pointer">
                <img src="/images/Logo.png" alt="Starscreen Logo" class="w-10 h-10">
                <span class="font-bold text-xl tracking-tight text-slate-800">Starscreen</span>
            </a>
            <div class="flex items-center gap-3" x-data="{ userMenuOpen: false, isAdmin: false, ...subscriptionStatus() }" x-init="loadSubscription(); isAdmin = Auth.getUser()?.is_admin || false">
                <template x-if="isAdmin">
                    <span class="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full font-semibold">ADMIN</span>
                </template>
                <span class="text-sm text-slate-500 bg-slate-100 px-3 py-1 rounded-full border border-slate-200">
                    v1.0 • Connected
                </span>

                <!-- User Dropdown Menu -->
                <div class="relative" @click.away="userMenuOpen = false">
                    <button @click="userMenuOpen = !userMenuOpen"
                            class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-100 transition">
                        <!-- Hamburger Icon (3 horizontal lines) -->
                        <svg class="w-6 h-6 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                        </svg>
                        <svg class="w-4 h-4 text-slate-500 transition-transform" :class="userMenuOpen ? 'rotate-180' : ''"
                             fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>

                    <!-- Dropdown Menu -->
                    <div x-show="userMenuOpen"
                         x-cloak
                         x-transition:enter="transition ease-out duration-100"
                         x-transition:enter-start="opacity-0 scale-95"
                         x-transition:enter-end="opacity-100 scale-100"
                         x-transition:leave="transition ease-in duration-75"
                         x-transition:leave-start="opacity-100 scale-100"
                         x-transition:leave-end="opacity-0 scale-95"
                         class="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-slate-200 py-2 z-50">

                        <!-- Subscription Info -->
                        <template x-if="subscription">
                            <div class="px-4 py-3 border-b border-slate-200">
                                <div class="flex items-center justify-between mb-3">
                                    <span class="text-xs font-medium text-slate-500 uppercase">Subscription</span>
                                    <span class="text-sm px-2.5 py-1 rounded-full border font-medium"
                                          :class="subscription.plan === 'free' ? 'bg-slate-100 border-slate-300 text-slate-700' : 'bg-brand-50 border-brand-300 text-brand-700'"
                                          x-text="subscription.plan_display"></span>
                                </div>

                                <!-- Usage Bar (if not unlimited) -->
                                <template x-if="subscription.monthly_candidate_limit < 900000">
                                    <div>
                                        <div class="flex justify-between items-baseline mb-1">
                                            <span class="text-xs text-slate-600">Candidates this month</span>
                                            <span class="text-sm font-bold text-slate-900" x-text="\`\${subscription.remaining_candidates} left\`"></span>
                                        </div>
                                        <div class="w-full bg-slate-200 rounded-full h-2 mb-1">
                                            <div class="h-2 rounded-full transition-all"
                                                 :class="{
                                                     'bg-red-500': subscription.usage_percentage >= 90,
                                                     'bg-yellow-500': subscription.usage_percentage >= 70 && subscription.usage_percentage < 90,
                                                     'bg-green-500': subscription.usage_percentage < 70
                                                 }"
                                                 :style="\`width: \${subscription.usage_percentage}%\`"></div>
                                        </div>
                                        <div class="flex justify-between text-xs text-slate-500">
                                            <span x-text="\`\${subscription.candidates_used_this_month} used\`"></span>
                                            <span x-text="\`\${subscription.monthly_candidate_limit} total\`"></span>
                                        </div>
                                        <template x-if="subscription.usage_percentage < 90 && subscription.current_period_end">
                                            <p class="text-xs text-slate-500 mt-2">
                                                Resets <span x-text="new Date(subscription.current_period_end).toLocaleDateString()"></span>
                                            </p>
                                        </template>
                                        <template x-if="subscription.usage_percentage >= 90">
                                            <p class="text-xs text-red-600 font-medium mt-2">
                                                ⚠️ Almost at limit! Consider upgrading.
                                            </p>
                                        </template>
                                    </div>
                                </template>

                                <!-- Unlimited Badge -->
                                <template x-if="subscription.monthly_candidate_limit >= 900000">
                                    <div class="flex items-center justify-center py-2">
                                        <div class="text-sm bg-gradient-to-r from-brand-500 to-purple-500 text-white px-4 py-2 rounded-full border border-brand-400 font-semibold">
                                            ∞ Unlimited Candidates
                                        </div>
                                    </div>
                                </template>
                            </div>
                        </template>

                        <!-- Menu Items -->
                        <div class="py-1">
                            <a href="/"
                               class="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
                                <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                                </svg>
                                Dashboard
                            </a>
                            <a href="/static/pricing.html"
                               class="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
                                <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"></path>
                                </svg>
                                Manage Billing
                            </a>
                            <a href="/static/settings.html"
                               class="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
                                <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                </svg>
                                Settings
                            </a>
                            <!-- Cancel Subscription (only show if user has paid plan) -->
                            <template x-if="subscription && subscription.plan !== 'free'">
                                <button @click.stop="window.cancelSubscriptionGlobal ? window.cancelSubscriptionGlobal() : cancelSubscription()"
                                        class="w-full flex items-center gap-3 px-4 py-2 text-sm text-orange-600 hover:bg-orange-50">
                                    <svg class="w-5 h-5 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                    </svg>
                                    Cancel Subscription
                                </button>
                            </template>
                            <a href="/static/privacy.html"
                               class="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
                                <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                                </svg>
                                Privacy Policy
                            </a>
                            <a href="/static/terms.html"
                               class="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
                                <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                </svg>
                                Terms of Service
                            </a>
                            <button @click.stop="window.deleteAccount()"
                                    class="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50">
                                <svg class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                                Delete Account
                            </button>
                        </div>

                        <!-- Logout -->
                        <div class="border-t border-slate-200 pt-1">
                            <button onclick="Auth.logout()"
                                    class="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
                                <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
                                </svg>
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</nav>
`;

/**
 * Render the navbar into a container element
 * @param {string} containerId - ID of the container element (default: 'navbar-container')
 */
function renderNavbar(containerId = 'navbar-container') {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = navbarHTML;
        console.log('Navbar rendered successfully');
    } else {
        console.error(`Navbar container #${containerId} not found`);
    }
}

// Export functions for use in pages
window.subscriptionStatus = subscriptionStatus;
window.renderNavbar = renderNavbar;
