import { Cookie, Lock, Mail, AlertTriangle } from 'lucide-react'
import { Card } from '@/components/ui/card'

export function CookiePolicy() {
  const lastUpdated = 'September 26, 2026'
  const version = '1.0'

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-12 px-4 sm:px-6 lg:px-8">
      <header className="text-center mb-12">
        <h1 className="text-4xl font-bold text-secondary-900 dark:text-white mb-4">Cookie Policy</h1>
        <div className="flex items-center justify-center gap-4 text-sm text-secondary-600 dark:text-secondary-400">
          <span>Version {version}</span>
          <span>•</span>
          <span>Last updated: {lastUpdated}</span>
        </div>
      </header>

      <section className="space-y-8">
        <Card className="bg-primary-50 dark:bg-primary-900/30 border-primary-200 dark:border-primary-800">
          <div className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-xl bg-primary-600 text-white">
                <Cookie className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-secondary-900 dark:text-white">Our Commitment</h2>
                <p className="text-primary-700 dark:text-primary-300 mt-1">
                  We use minimal cookies only for essential functionality. No tracking, advertising, or third-party analytics cookies.
                </p>
              </div>
            </div>
          </div>
        </Card>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">1. What Are Cookies?</h2>
            <Card>
              <div className="p-6">
                <p className="text-secondary-700 dark:text-secondary-300">
                  Cookies are small text files stored on your device when you visit a website. They help websites remember your preferences, authenticate sessions, and understand how the site is used.
                </p>
                <div className="mt-4 p-4 bg-secondary-50 dark:bg-secondary-800/50 rounded-lg">
                  <p className="text-secondary-700 dark:text-secondary-300">
                    <strong>RIFT uses only first-party, essential cookies.</strong> We do not use third-party tracking cookies, advertising cookies, or analytics cookies from external providers.
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">2. Types of Cookies We Use</h2>
            <Card>
              <div className="p-6 space-y-6">
                <div className="border-l-4 border-primary-500 pl-4">
                  <h3 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">Essential Cookies (Always Active)</h3>
                  <p className="text-secondary-700 dark:text-secondary-300 mb-3">Required for the platform to function. Cannot be disabled.</p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-secondary-200 dark:border-secondary-700">
                        <th className="text-left p-3 font-semibold">Cookie Name</th>
                        <th className="text-left p-3 font-semibold">Purpose</th>
                        <th className="text-left p-3 font-semibold">Duration</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-secondary-100 dark:divide-secondary-800">
                      <tr>
                        <td className="p-3 font-mono">rift_session</td>
                        <td className="p-3">Session authentication</td>
                        <td className="p-3">Session</td>
                      </tr>
                      <tr>
                        <td className="p-3 font-mono">rift_csrf</td>
                        <td className="p-3">CSRF protection</td>
                        <td className="p-3">Session</td>
                      </tr>
                      <tr>
                        <td className="p-3 font-mono">rift_theme</td>
                        <td className="p-3">Theme preference (light/dark/system)</td>
                        <td className="p-3">1 year</td>
                      </tr>
                      <tr>
                        <td className="p-3 font-mono">rift_consent</td>
                        <td className="p-3">Cookie consent preferences</td>
                        <td className="p-3">1 year</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="border-l-4 border-success-500 pl-4">
                  <h3 className="font-semibold text-success-800 dark:text-success-200 mb-2">Preference Cookies (Optional)</h3>
                  <p className="text-secondary-700 dark:text-secondary-300 mb-3">Remember your preferences. Can be disabled.</p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-secondary-200 dark:border-secondary-700">
                        <th className="text-left p-3 font-semibold">Cookie Name</th>
                        <th className="text-left p-3 font-semibold">Purpose</th>
                        <th className="text-left p-3 font-semibold">Duration</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-secondary-100 dark:divide-secondary-800">
                      <tr>
                        <td className="p-3 font-mono">rift_sidebar</td>
                        <td className="p-3">Sidebar open/closed state</td>
                        <td className="p-3">1 year</td>
                      </tr>
                      <tr>
                        <td className="p-3 font-mono">rift_view_mode</td>
                        <td className="p-3">Grid/list view preference</td>
                        <td className="p-3">1 year</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">3. What We DON'T Use</h2>
            <Card className="bg-error-50 dark:bg-error-900/30 border-error-200 dark:border-error-800">
              <div className="p-6">
                <div className="flex items-start gap-3 mb-4">
                  <AlertTriangle className="w-6 h-6 text-error-600 dark:text-error-400 flex-shrink-0" />
                  <div>
                    <h3 className="font-semibold text-error-800 dark:text-error-200 mb-2">We Do NOT Use</h3>
                    <ul className="space-y-2 list-disc list-inside text-error-700 dark:text-error-300">
                      <li>Google Analytics, Mixpanel, or any third-party analytics</li>
                      <li>Advertising or marketing cookies (Facebook Pixel, Google Ads, etc.)</li>
                      <li>Social media tracking (Facebook, Twitter, LinkedIn pixels)</li>
                      <li>Session replay or heatmap tools (Hotjar, FullStory, etc.)</li>
                      <li>Cross-site tracking or fingerprinting</li>
                      <li>Third-party embeds that set cookies</li>
                    </ul>
                  </div>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">3. Cookie Consent</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  We use a simple, transparent cookie banner that appears on your first visit. You can:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li>Accept all cookies (essential + preferences)</li>
                  <li>Reject non-essential cookies (only essential cookies will be set)</li>
                  <li>Customize your preferences per category</li>
                  <li>Change your mind anytime via the cookie settings link in the footer</li>
                </ul>
                <div className="mt-4 p-4 bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800 rounded-lg">
                  <p className="text-primary-800 dark:text-primary-200">
                    <strong>Essential cookies cannot be disabled</strong> as they are required for the platform to function (authentication, security, basic preferences).
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">4. Managing Cookies</h2>
            <Card>
              <div className="p-6 space-y-4">
                <h3 className="font-semibold text-secondary-900 dark:text-white mb-3">Browser Controls</h3>
                <p className="text-secondary-700 dark:text-secondary-300 mb-4">
                  All modern browsers allow you to manage cookies:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li>Chrome: Settings → Privacy and security → Cookies and other site data</li>
                  <li>Firefox: Options → Privacy & Security → Cookies and Site Data</li>
                  <li>Safari: Preferences → Privacy → Manage Website Data</li>
                  <li>Edge: Settings → Cookies and site permissions</li>
                </ul>
                <h3 className="font-semibold text-secondary-900 dark:text-white mb-3 mt-6">Our Cookie Settings</h3>
                <p className="text-secondary-700 dark:text-secondary-300 mb-3">
                  You can also manage your cookie preferences directly in RIFT:
                </p>
                <ol className="space-y-2 list-decimal list-inside text-secondary-700 dark:text-secondary-300">
                  <li>Click the cookie icon in the footer or footer link "Cookie Settings"</li>
                  <li>Toggle preference cookies on/off</li>
                  <li>Changes apply immediately (page reload may be required)</li>
                </ol>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">5. Data Protection</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  Cookie data is considered personal data under GDPR, DPDP, and similar regulations. We protect it as follows:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li>Essential cookies: Stored securely, HttpOnly, Secure, SameSite=Lax</li>
                  <li>Preference cookies: SameSite=Lax, no sensitive data stored</li>
                  <li>No cookie data shared with third parties</li>
                  <li>Cookie consent logged with timestamp for compliance</li>
                  <li>Data retention: 1 year for preferences, session for auth</li>
                </ul>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">6. Third-Party Embeds</h2>
            <Card>
              <div className="p-6">
                <p className="text-secondary-700 dark:text-secondary-300 mb-4">
                  RIFT does not embed third-party content that sets cookies. If we add integrations in the future:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li>We will review their cookie practices before integration</li>
                  <li>We will only use providers with GDPR/DPDP-compliant DPAs</li>
                  <li>You will be notified and asked for consent before any new cookies are set</li>
                  <li>We will update this policy before any changes take effect</li>
                </ul>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">7. Changes to This Policy</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  We may update this policy to reflect changes in our cookie practices or legal requirements. We will notify you of material changes via email (if you have an account) or through a prominent notice on the platform at least 30 days before they take effect.
                </p>
                <div className="p-4 bg-secondary-50 dark:bg-secondary-800/50 rounded-lg">
                  <p className="text-sm text-secondary-600 dark:text-secondary-400">
                    <strong>Current Version:</strong> {version} • <strong>Last Updated:</strong> {lastUpdated}
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">7. Contact Us</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  Questions about our cookie practices?
                </p>
                <dl className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Mail className="w-5 h-5 text-primary-600 dark:text-primary-400 flex-shrink-0" />
                    <div>
                      <dt className="font-medium text-secondary-900 dark:text-white">Email</dt>
                      <dd className="text-secondary-600 dark:text-secondary-400">
                        <a href="mailto:privacy@rift.dev" className="underline hover:no-underline">privacy@rift.dev</a>
                      </dd>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                      <Lock className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div>
                      <dt className="font-medium text-secondary-900 dark:text-white">Data Protection Officer</dt>
                      <dd className="text-secondary-600 dark:text-secondary-400">Available at privacy@rift.dev</dd>
                    </div>
                  </div>
                </dl>
              </div>
            </Card>
          </section>
        </section>
      </div>
  )
}