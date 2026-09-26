import { Shield, Lock, Mail, Clock, AlertTriangle } from 'lucide-react'
import { Card } from '@/components/ui/card'

export function PrivacyPolicy() {
  const lastUpdated = 'September 26, 2026'
  const version = '1.0'

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-12 px-4 sm:px-6 lg:px-8">
      <header className="text-center mb-12">
        <h1 className="text-4xl font-bold text-secondary-900 dark:text-white mb-4">Privacy Policy</h1>
        <div className="flex items-center justify-center gap-4 text-sm text-secondary-600 dark:text-secondary-400">
          <span>Version {version}</span>
          <span>•</span>
          <span>Last updated: {lastUpdated}</span>
          <span>•</span>
          <span>Effective: {lastUpdated}</span>
        </div>
      </header>

      <section className="space-y-6">
        <Card className="bg-primary-50 dark:bg-primary-900/30 border-primary-200 dark:border-primary-800">
          <div className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-xl bg-primary-600 text-white">
                <Shield className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-secondary-900 dark:text-white">Our Commitment</h2>
                <p className="text-primary-700 dark:text-primary-300 mt-1">
                  RIFT is a research prototype. We are committed to protecting your privacy and being transparent about how we handle data.
                </p>
              </div>
            </div>
          </div>
        </Card>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">1. Data We Collect</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-600 dark:text-secondary-400">
                  RIFT is a research prototype. We collect minimal data necessary for the platform to function:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li><strong>Account Data:</strong> Email, name, organization (if you create an account)</li>
                  <li><strong>Usage Data:</strong> API requests, simulation runs, feature usage (anonymized)</li>
                  <li><strong>Technical Data:</strong> IP address, browser type, OS, timestamps (for security)</li>
                  <li><strong>No Real Patient Data:</strong> No real patient data is committed to or stored in this build. All clinical data is synthetic or from open-access public datasets (PhysioNet, etc.) with proper licensing.</li>
                </ul>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">2. How We Use Your Data</h2>
            <Card>
              <div className="p-6 space-y-4">
                <ul className="space-y-3 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li><strong>Service Provision:</strong> To provide the RIFT platform, run simulations, and generate evidence bundles</li>
                  <li><strong>Improvement:</strong> Anonymized usage analytics to improve the platform</li>
                  <li><strong>Security:</strong> Fraud prevention, abuse detection, system integrity</li>
                  <li><strong>Legal Compliance:</strong> Fulfilling legal obligations, responding to valid requests</li>
                  <li><strong>No Sale:</strong> We do not sell your personal data to third parties</li>
                  <li><strong>No Marketing:</strong> We do not use your data for marketing without explicit consent</li>
                </ul>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">3. Data Sharing</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">We do not sell your data. We may share data only in these circumstances:</p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li><strong>Service Providers:</strong> Cloud hosting (Supabase), payment processing (Lemon Squeezy), error tracking — under strict DPAs</li>
                  <li><strong>Legal Requirements:</strong> When required by law, court order, or government request</li>
                  <li><strong>Business Transfers:</strong> In case of merger/acquisition (with notice and same protections)</li>
                  <li><strong>Research Collaborators:</strong> Only with explicit consent and appropriate agreements</li>
                </ul>
                <div className="mt-4 p-4 bg-warning-50 dark:bg-warning-900/30 border border-warning-200 dark:border-warning-800 rounded-lg">
                  <p className="text-warning-800 dark:text-warning-200">
                    <strong>No Real Patient Data:</strong> No real patient data is committed to or stored in this build. All clinical data is synthetic or from open-access public datasets (PhysioNet, etc.) with proper licensing.
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">4. Data Retention</h2>
            <Card>
              <div className="p-6 space-y-4">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-secondary-200 dark:border-secondary-700">
                      <th className="text-left p-3 font-semibold">Data Category</th>
                      <th className="text-left p-3 font-semibold">Retention Period</th>
                      <th className="text-left p-3 font-semibold">Basis</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-secondary-100 dark:divide-secondary-800">
                    <tr>
                      <td className="p-3">Account Data</td>
                      <td className="p-3">Account lifetime + 30 days after deletion</td>
                      <td className="p-3">Contract performance</td>
                    </tr>
                    <tr>
                      <td className="p-3">Simulation Runs & Results</td>
                      <td className="p-3">2 years (configurable)</td>
                      <td className="p-3">Research reproducibility</td>
                    </tr>
                    <tr>
                      <td className="p-3">Audit Logs</td>
                      <td className="p-3">7 years</td>
                      <td className="p-3">Legal compliance</td>
                    </tr>
                    <tr>
                      <td className="p-3">Analytics (Anonymized)</td>
                      <td className="p-3">Indefinite (aggregated)</td>
                      <td className="p-3">Product improvement</td>
                    </tr>
                    <tr>
                      <td className="p-3">Backup Data</td>
                      <td className="p-3">30 days</td>
                      <td className="p-3">Disaster recovery</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">5. Your Rights</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  Under GDPR, DPDP (India), and other applicable laws, you have the following rights:
                </p>
                <ul className="space-y-3 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li><strong>Access:</strong> Request a copy of your personal data</li>
                  <li><strong>Rectification:</strong> Correct inaccurate or incomplete data</li>
                  <li><strong>Erasure:</strong> Request deletion (right to be forgotten)</li>
                  <li><strong>Restriction:</strong> Limit how we process your data</li>
                  <li><strong>Portability:</strong> Receive your data in a portable format</li>
                  <li><strong>Objection:</strong> Object to processing for direct marketing or legitimate interests</li>
                  <li><strong>Withdraw Consent:</strong> Withdraw consent at any time (where consent is the basis)</li>
                  <li><strong>Automated Decisions:</strong> Right to not be subject to solely automated decisions with legal effects</li>
                </ul>
                <div className="mt-4 p-4 bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800 rounded-lg">
                  <p className="text-primary-800 dark:text-primary-200">
                    <strong>To exercise your rights:</strong> Contact us at <a href="mailto:privacy@rift.dev" className="underline">privacy@rift.dev</a> or use the account settings page. We respond within 30 days.
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">6. International Transfers</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  RIFT is hosted on infrastructure that may involve international data transfers. We ensure adequate protection through:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li><strong>Adequacy Decisions:</strong> Transfers to countries with EU adequacy decisions</li>
                  <li><strong>Standard Contractual Clauses (SCCs):</strong> EU Commission-approved SCCs for other transfers</li>
                  <li><strong>Supplementary Measures:</strong> Encryption, pseudonymization, and organizational measures where needed</li>
                  <li><strong>Data Processing Agreements:</strong> All subprocessors have signed DPAs with appropriate safeguards</li>
                </ul>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">7. Security</h2>
            <Card>
              <div className="p-6 space-y-4">
                <ul className="space-y-3 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li><strong>Encryption:</strong> TLS 1.3 in transit, AES-256 at rest</li>
                  <li><strong>Authentication:</strong> JWT with HS256, Supabase Auth, optional MFA</li>
                  <li><strong>Access Control:</strong> RBAC with per-row ownership enforcement</li>
                  <li><strong>API Security:</strong> Rate limiting, HMAC webhook verification, SSRF protection</li>
                  <li><strong>Monitoring:</strong> Real-time alerting, audit logging, anomaly detection</li>
                  <li><strong>Incident Response:</strong> Documented IR plan, 72-hour breach notification</li>
                  <li><strong>Penetration Testing:</strong> Annual third-party assessments</li>
                </ul>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">8. Children's Privacy</h2>
            <Card>
              <div className="p-6">
                <p className="text-secondary-700 dark:text-secondary-300">
                  RIFT is a research platform for professionals. We do not knowingly collect data from children under 16 (or the applicable age in your jurisdiction). If you believe we have collected data from a child, contact us immediately at privacy@rift.dev.
                </p>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">9. International Compliance</h2>
            <Card>
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800">
                    <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">GDPR (EU)</h4>
                    <ul className="space-y-1 text-sm text-secondary-700 dark:text-secondary-300 list-disc list-inside">
                      <li>Lawful basis documented for all processing</li>
                      <li>DPIA completed for high-risk processing</li>
                      <li>DPO appointed: privacy@rift.dev</li>
                      <li>Records of processing activities maintained</li>
                    </ul>
                  </div>
                  <div className="p-4 rounded-lg bg-primary-50 dark:bg-primary-900/30 border-primary-200 dark:border-primary-800">
                    <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">DPDP Act (India)</h4>
                    <ul className="space-y-1 text-sm text-secondary-700 dark:text-secondary-300 list-disc list-inside">
                      <li>Consent manager framework compliant</li>
                      <li>Data Principal rights implementation</li>
                      <li>Grievance officer appointed</li>
                      <li>Data localization for sensitive data</li>
                    </ul>
                  </div>
                  <div className="p-4 rounded-lg bg-primary-50 dark:bg-primary-900/30 border-primary-200 dark:border-primary-800">
                    <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">CCPA/CPRA (California)</h4>
                    <ul className="space-y-1 text-sm text-secondary-700 dark:text-secondary-300 list-disc list-inside">
                      <li>No sale of personal information</li>
                      <li>Right to know, delete, opt-out implemented</li>
                      <li>No financial incentives for data</li>
                    </ul>
                  </div>
                  <div className="p-4 rounded-lg bg-primary-50 dark:bg-primary-900/30 border-primary-200 dark:border-primary-800">
                    <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">Other Jurisdictions</h4>
                    <ul className="space-y-1 text-sm text-secondary-700 dark:text-secondary-300 list-disc list-inside">
                      <li>LGPD (Brazil) — adequacy assessment</li>
                      <li>PIPL (China) — cross-border rules</li>
                      <li>POPIA (South Africa) — compliance review</li>
                      <li>APPI (Japan) — cross-border framework</li>
                    </ul>
                  </div>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">10. Changes to This Policy</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  We may update this policy to reflect changes in our practices or legal requirements. We will notify you of material changes via email (if you have an account) or through a prominent notice on the platform at least 30 days before they take effect.
                </p>
                <p className="text-secondary-700 dark:text-secondary-300">
                  Your continued use of RIFT after the effective date constitutes acceptance of the updated policy.
                </p>
                <div className="p-4 bg-secondary-50 dark:bg-secondary-800/50 rounded-lg">
                  <p className="text-sm text-secondary-600 dark:text-secondary-400">
                    <strong>Current Version:</strong> {version} • <strong>Last Updated:</strong> {new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">11. Contact Us</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  For privacy questions, complaints, or to exercise your rights:
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
                      <dd className="text-secondary-600 dark:text-secondary-400">Available at the above email</dd>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                      <Clock className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div>
                      <dt className="font-medium text-secondary-900 dark:text-white">Response Time</dt>
                      <dd className="text-secondary-600 dark:text-secondary-400">Within 30 days (GDPR) / 45 days (DPDP)</dd>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-warning-100 dark:bg-warning-900/30">
                      <AlertTriangle className="w-5 h-5 text-warning-600 dark:text-warning-400" />
                    </div>
                    <div>
                      <dt className="font-medium text-secondary-900 dark:text-white">Supervisory Authority</dt>
                      <dd className="text-secondary-600 dark:text-secondary-400">
                        You have the right to lodge a complaint with your local data protection authority
                      </dd>
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