import { Shield, AlertTriangle, Mail, Scale } from 'lucide-react'
import { Card } from '@/components/ui/card'

export function TermsOfService() {
  const lastUpdated = 'September 26, 2026'
  const version = '1.0'

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-12 px-4 sm:px-6 lg:px-8">
      <header className="text-center mb-12">
        <h1 className="text-4xl font-bold text-secondary-900 dark:text-white mb-4">Terms of Service</h1>
        <div className="flex items-center justify-center gap-4 text-sm text-secondary-600 dark:text-secondary-400">
          <span>Version {version}</span>
          <span>•</span>
          <span>Last updated: {lastUpdated}</span>
          <span>•</span>
          <span>Effective: {lastUpdated}</span>
        </div>
      </header>

      <section className="space-y-8">
        <Card className="bg-primary-50 dark:bg-primary-900/30 border-primary-200 dark:border-primary-800">
          <div className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-xl bg-primary-600 text-white">
                <Shield className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-secondary-900 dark:text-white">Important Notice</h2>
                <p className="text-primary-700 dark:text-primary-300 mt-1">
                  RIFT is a <strong>research prototype</strong>. It is not clinically validated, not FDA-cleared, not CE-marked, and not approved for clinical use. All clinical data is synthetic or from open-access public datasets. Do not use for clinical decision-making.
                </p>
              </div>
            </div>
          </div>
        </Card>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">1. Acceptance of Terms</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  By accessing or using RIFT ("the Platform"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree, do not use the Platform.
                </p>
                <p className="text-secondary-700 dark:text-secondary-300">
                  These Terms constitute a legally binding agreement between you ("User") and RIFT ("we", "us", "our"). We may update these Terms at any time. Continued use after changes constitutes acceptance.
                </p>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">2. Research Prototype Disclaimer</h2>
            <Card>
              <div className="p-6 space-y-4">
                <div className="p-4 bg-warning-50 dark:bg-warning-900/30 border border-warning-200 dark:border-warning-800 rounded-lg">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-warning-600 dark:text-warning-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-warning-800 dark:text-warning-200 mb-2">Critical Disclaimer</h4>
                      <ul className="space-y-2 list-disc list-inside text-warning-700 dark:text-warning-300">
                        <li>RIFT is a <strong>research prototype</strong> — not clinically validated</li>
                        <li><strong>Not FDA-cleared</strong>, not CE-marked, not approved for clinical use</li>
                        <li>All clinical data is <strong>synthetic or from open-access public datasets</strong></li>
                        <li><strong>No clinical decision-making</strong> — decision support only, human-in-the-loop required</li>
                        <li>Quantum features are <strong>experimental</strong> — no quantum advantage demonstrated</li>
                        <li>Results are for <strong>research and educational purposes only</strong></li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">3. License Grant</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  Subject to these Terms, we grant you a limited, non-exclusive, non-transferable, revocable license to:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li>Access and use the Platform for research and educational purposes</li>
                  <li>Run simulations and generate evidence bundles for evaluation</li>
                  <li>Export evidence bundles in JSON format for analysis</li>
                  <li>Use the API for integration with your research workflows</li>
                </ul>
                <div className="p-4 bg-error-50 dark:bg-error-900/30 border border-error-200 dark:border-error-800 rounded-lg">
                  <h4 className="font-semibold text-error-800 dark:text-error-200 mb-2">Restrictions</h4>
                  <ul className="space-y-1 list-disc list-inside text-error-700 dark:text-error-300">
                    <li>No clinical use, patient care, or medical decision-making</li>
                    <li>No reverse engineering, decompilation, or disassembly</li>
                    <li>No removal of copyright, trademark, or proprietary notices</li>
                    <li>No sublicensing, resale, or commercial exploitation</li>
                    <li>No use in violation of applicable laws or regulations</li>
                    <li>No training AI/ML models on Platform output without explicit permission</li>
                  </ul>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">4. Intellectual Property</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  All rights, title, and interest in the Platform (including software, algorithms, models, documentation, and trademarks) are owned by RIFT or its licensors. You acquire no ownership rights.
                </p>
                <p className="text-secondary-700 dark:text-secondary-300">
                  RIFT is licensed under AGPL-3.0-or-later. See <a href="https://github.com/OpKnock/RIFT/blob/main/LICENSE" className="underline hover:no-underline" target="_blank" rel="noopener noreferrer">LICENSE</a> for details.
                </p>
                <div className="p-4 bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800 rounded-lg">
                  <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">Open Source Components</h4>
                  <p className="text-sm text-secondary-700 dark:text-secondary-300">
                    RIFT incorporates open-source software. See <a href="https://github.com/OpKnock/RIFT/blob/main/THIRD-PARTY-NOTICES" className="underline hover:no-underline" target="_blank" rel="noopener noreferrer">THIRD-PARTY-NOTICES</a> for attributions and licenses.
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">5. User Responsibilities</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  You agree to:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li>Use the Platform only for lawful, research, and educational purposes</li>
                  <li>Maintain the security of your credentials and API keys</li>
                  <li>Not attempt to gain unauthorized access to systems or data</li>
                  <li>Not interfere with the Platform's operation or other users</li>
                  <li>Comply with all applicable laws, regulations, and ethical guidelines</li>
                  <li>Report security vulnerabilities via <a href="mailto:security@rift.dev" className="underline hover:no-underline">security@rift.dev</a></li>
                  <li>Not use the Platform for clinical decision-making or patient care</li>
                  <li>Acknowledge the research prototype nature in any publications</li>
                </ul>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">6. Disclaimer of Warranties</h2>
            <Card className="bg-error-50 dark:bg-error-900/30 border-error-200 dark:border-error-800">
              <div className="p-6 space-y-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-6 h-6 text-error-600 dark:text-error-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-error-800 dark:text-error-200 mb-3">THE PLATFORM IS PROVIDED "AS IS" AND "AS AVAILABLE"</h4>
                    <p className="text-error-700 dark:text-error-300 mb-3">
                      TO THE MAXIMUM EXTENT PERMITTED BY LAW, RIFT DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO:
                    </p>
                    <ul className="space-y-2 list-disc list-inside text-error-700 dark:text-error-300">
                      <li>MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE</li>
                      <li>NON-INFRINGEMENT</li>
                      <li>ACCURACY, RELIABILITY, OR CORRECTNESS OF RESULTS</li>
                      <li>UNINTERRUPTED OR ERROR-FREE OPERATION</li>
                      <li>CLINICAL VALIDITY OR MEDICAL UTILITY</li>
                      <li>QUANTUM ADVANTAGE OR SUPERIORITY OVER CLASSICAL METHODS</li>
                    </ul>
                    <p className="text-error-700 dark:text-error-300 mt-3">
                      THE ENTIRE RISK AS TO QUALITY AND PERFORMANCE IS WITH YOU.
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">7. Limitation of Liability</h2>
            <Card className="bg-error-50 dark:bg-error-900/30 border-error-200 dark:border-error-800">
              <div className="p-6 space-y-4">
                <p className="text-error-700 dark:text-error-300">
                  TO THE MAXIMUM EXTENT PERMITTED BY LAW, RIFT SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO:
                </p>
                <ul className="space-y-2 list-disc list-inside text-error-700 dark:text-error-300">
                  <li>LOSS OF DATA, REVENUE, PROFITS, OR GOODWILL</li>
                  <li>BUSINESS INTERRUPTION</li>
                  <li>CLINICAL HARM OR PATIENT INJURY</li>
                  <li>COST OF SUBSTITUTE GOODS OR SERVICES</li>
                </ul>
                <p className="text-error-700 dark:text-error-300 mt-4">
                  OUR TOTAL AGGREGATE LIABILITY SHALL NOT EXCEED THE GREATER OF: (A) AMOUNTS PAID BY YOU IN THE 12 MONTHS PRECEDING THE CLAIM, OR (B) $100 USD.
                </p>
                <p className="text-error-700 dark:text-error-300 mt-4">
                  SOME JURISDICTIONS DO NOT ALLOW LIMITATION OF LIABILITY. IN SUCH CASES, OUR LIABILITY IS LIMITED TO THE MAXIMUM EXTENT PERMITTED BY LAW.
                </p>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">8. Indemnification</h2>
            <Card>
              <div className="p-6">
                <p className="text-secondary-700 dark:text-secondary-300">
                  You agree to indemnify, defend, and hold harmless RIFT and its officers, directors, employees, and agents from and against any claims, damages, losses, liabilities, costs, and expenses (including reasonable attorneys' fees) arising from:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300 mt-4">
                  <li>Your use of the Platform in violation of these Terms</li>
                  <li>Your violation of any law or third-party rights</li>
                  <li>Your clinical use of the Platform resulting in harm</li>
                  <li>Your submission of inaccurate, illegal, or harmful data</li>
                </ul>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">9. Termination</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  We may suspend or terminate your access at any time, with or without cause, with or without notice, effective immediately. Upon termination:
                </p>
                <ul className="space-y-2 list-disc list-inside text-secondary-700 dark:text-secondary-300">
                  <li>Your license terminates immediately</li>
                  <li>You must cease all use of the Platform</li>
                  <li>We may delete your data per our retention policy</li>
                  <li>Sections 3, 4, 6, 7, 8, 9, 10, 11, 12 survive termination</li>
                </ul>
                <p className="text-secondary-700 dark:text-secondary-300 mt-4">
                  You may terminate your account at any time via the Settings page or by contacting us.
                </p>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">10. Governing Law & Dispute Resolution</h2>
            <Card>
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800">
                    <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">Governing Law</h4>
                    <p className="text-sm text-secondary-700 dark:text-secondary-300">
                      These Terms are governed by the laws of the State of Delaware, USA, without regard to conflict of laws principles.
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800">
                    <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">Dispute Resolution</h4>
                    <p className="text-sm text-secondary-700 dark:text-secondary-300">
                      Good faith negotiation → Mediation → Binding arbitration (ICDR rules, Delaware seat, English language) → Courts of Delaware for injunctive relief.
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800">
                    <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">Class Action Waiver</h4>
                    <p className="text-sm text-secondary-700 dark:text-secondary-300">
                      Disputes resolved individually. No class actions, consolidated actions, or representative proceedings.
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800">
                    <h4 className="font-semibold text-primary-800 dark:text-primary-200 mb-2">Small Claims</h4>
                    <p className="text-sm text-secondary-700 dark:text-secondary-300">
                      Either party may bring individual claims in small claims court instead of arbitration.
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">11. Export Control & Sanctions</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  You may not use the Platform if you are located in, a national of, or acting on behalf of any country subject to US, EU, or UN sanctions (including Cuba, Iran, North Korea, Syria, Crimea, Russia, Belarus). You are not a denied party on any government watchlist.
                </p>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">12. General Provisions</h2>
            <Card>
              <div className="p-6 space-y-4">
                <dl className="space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <dt className="font-semibold text-secondary-900 dark:text-white">Entire Agreement</dt>
                      <dd className="text-secondary-700 dark:text-secondary-300 mt-1">These Terms, Privacy Policy, and referenced documents constitute the entire agreement.</dd>
                    </div>
                    <div>
                      <dt className="font-semibold text-secondary-900 dark:text-white">Severability</dt>
                      <dd className="text-secondary-700 dark:text-secondary-300 mt-1">If any provision is unenforceable, the remainder remains in effect.</dd>
                    </div>
                    <div>
                      <dt className="font-semibold text-secondary-900 dark:text-white">Waiver</dt>
                      <dd className="text-secondary-700 dark:text-secondary-300 mt-1">Failure to enforce a right is not a waiver of that right.</dd>
                    </div>
                    <div>
                      <dt className="font-semibold text-secondary-900 dark:text-white">Assignment</dt>
                      <dd className="text-secondary-700 dark:text-secondary-300 mt-1">You may not assign these Terms. We may assign freely.</dd>
                    </div>
                    <div>
                      <dt className="font-semibold text-secondary-900 dark:text-white">Force Majeure</dt>
                      <dd className="text-secondary-700 dark:text-secondary-300 mt-1">We are not liable for delays due to events beyond our control.</dd>
                    </div>
                    <div>
                      <dt className="font-semibold text-secondary-900 dark:text-white">Notices</dt>
                      <dd className="text-secondary-700 dark:text-secondary-300 mt-1">Via email, in-app notification, or Platform posting.</dd>
                    </div>
                  </div>
                  </dl>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">13. Contact</h2>
            <Card>
              <div className="p-6 space-y-4">
                <p className="text-secondary-700 dark:text-secondary-300">
                  Questions about these Terms? Contact us:
                </p>
                <dl className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Mail className="w-5 h-5 text-primary-600 dark:text-primary-400 flex-shrink-0" />
                    <div>
                      <dt className="font-medium text-secondary-900 dark:text-white">Legal</dt>
                      <dd className="text-secondary-600 dark:text-secondary-400">
                        <a href="mailto:legal@rift.dev" className="underline hover:no-underline">legal@rift.dev</a>
                      </dd>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                      <Scale className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div>
                      <dt className="font-medium text-secondary-900 dark:text-white">Data Protection Officer</dt>
                      <dd className="text-secondary-600 dark:text-secondary-400">privacy@rift.dev</dd>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                      <Shield className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div>
                      <dt className="font-medium text-secondary-900 dark:text-white">Security</dt>
                      <dd className="text-secondary-600 dark:text-secondary-400">security@rift.dev</dd>
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