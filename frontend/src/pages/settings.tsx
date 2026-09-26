import { User, Shield, Bell, Palette, Key, Globe, Database, Trash2, Moon, Sun, Monitor, Save, Zap, CreditCard, Github, MessageSquare, AlertTriangle, Download } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export function Settings() {
  const [activeTab, setActiveTab] = useState('profile')
  const [loading] = useState(false)

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'api', label: 'API Keys', icon: Key },
    { id: 'integrations', label: 'Integrations', icon: Globe },
    { id: 'data', label: 'Data & Privacy', icon: Database },
    { id: 'danger', label: 'Danger Zone', icon: Trash2 },
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6 py-6 px-4 sm:px-6 lg:px-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Settings</h1>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1">Manage your account and preferences</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4 md:grid-cols-8 gap-1 p-1 bg-secondary-100 dark:bg-secondary-800 rounded-lg">
          {tabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="flex items-center gap-2 px-3 py-2">
              <tab.icon className="w-4 h-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="profile" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Profile Information</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input label="Full Name" placeholder="John Doe" defaultValue="Research User" />
                <Input label="Email" type="email" placeholder="user@example.com" defaultValue="research@rift.dev" />
                <Input label="Organization" placeholder="Your organization" defaultValue="RIFT Research" />
                <Input label="Role" placeholder="Your role" defaultValue="Researcher" />
              </div>
              <div className="flex items-center gap-4 pt-4 border-t border-secondary-100 dark:border-secondary-800">
                <Button onClick={() => {}} disabled={loading}>
                  <Save className="w-4 h-4 mr-2" />
                  Save Changes
                </Button>
                <Button variant="outline">Cancel</Button>
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Avatar</h2>
              <div className="flex items-center gap-4">
                <div className="w-20 h-20 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center overflow-hidden">
                  <span className="text-2xl font-bold text-primary-600 dark:text-primary-400">RU</span>
                </div>
                <div>
                  <Button variant="outline">Change Avatar</Button>
                  <p className="text-sm text-secondary-500 dark:text-secondary-400 mt-1">JPG, PNG or GIF. Max 2MB.</p>
                </div>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Password</h2>
              <div className="space-y-4">
                <Input label="Current Password" type="password" placeholder="Enter current password" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input label="New Password" type="password" placeholder="Enter new password" />
                  <Input label="Confirm Password" type="password" placeholder="Confirm new password" />
                </div>
                <Button onClick={() => {}} disabled={loading}>
                  <Save className="w-4 h-4 mr-2" />
                  Update Password
                </Button>
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Two-Factor Authentication</h2>
              <p className="text-secondary-600 dark:text-secondary-400">Add an extra layer of security to your account.</p>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-secondary-900 dark:text-white">Authenticator App</h3>
                  <p className="text-secondary-600 dark:text-secondary-400 text-sm">Use Google Authenticator, Authy, or similar</p>
                </div>
                <Button variant="outline">Enable 2FA</Button>
              </div>
            </div>
          </Card>

          <Card className="border-error-200 dark:border-error-800">
            <div className="p-6 space-y-4">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Active Sessions</h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-4 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
                      <Monitor className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div>
                      <p className="font-medium text-secondary-900 dark:text-white">Current Session</p>
                      <p className="text-sm text-secondary-500 dark:text-secondary-400">Chrome on Windows • Active now</p>
                    </div>
                  </div>
                  <Badge variant="success">Current</Badge>
                </div>
                <div className="flex items-center justify-between p-4 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-secondary-100 dark:bg-secondary-800 flex items-center justify-center">
                      <Monitor className="w-5 h-5 text-secondary-600 dark:text-secondary-400" />
                    </div>
                    <div>
                      <p className="font-medium text-secondary-900 dark:text-white">Mobile Session</p>
                      <p className="text-sm text-secondary-500 dark:text-secondary-400">Safari on iOS • 2 hours ago</p>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" className="text-error-600 dark:text-error-400 hover:text-error-700 dark:hover:text-error-300">Revoke</Button>
                </div>
              </div>
              <Button variant="ghost" className="w-full text-error-600 dark:text-error-400 hover:text-error-700 dark:hover:text-error-300">
                <Trash2 className="w-4 h-4 mr-2" />
                Revoke All Other Sessions
              </Button>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Email Notifications</h2>
              <div className="space-y-4">
                {[
                  { label: 'Simulation completed', description: 'When a simulation finishes', enabled: true },
                  { label: 'Experiment completed', description: 'When an experiment finishes', enabled: true },
                  { label: 'Evidence bundle ready', description: 'When evidence bundle is generated', enabled: true },
                  { label: 'Guardian alerts', description: 'When Guardian withholds a result', enabled: true },
                  { label: 'Weekly summary', description: 'Weekly activity digest', enabled: false },
                  { label: 'Security alerts', description: 'Security-related notifications', enabled: true },
                  { label: 'Product updates', description: 'New features and announcements', enabled: false },
                ].map((notification, index) => (
                  <div key={index} className="flex items-center justify-between py-3 border-b border-secondary-100 dark:border-secondary-800 last:border-0">
                    <div className="flex-1">
                      <p className="font-medium text-secondary-900 dark:text-white">{notification.label}</p>
                      <p className="text-sm text-secondary-500 dark:text-secondary-400">{notification.description}</p>
                    </div>
                    <Switch checked={notification.enabled} onChange={() => {}} />
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-4">In-App Notifications</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-secondary-900 dark:text-white">Push Notifications</p>
                    <p className="text-sm text-secondary-500 dark:text-secondary-400">Receive browser push notifications</p>
                  </div>
                  <Switch checked={true} onChange={() => {}} />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-secondary-900 dark:text-white">Sound</p>
                    <p className="text-sm text-secondary-500 dark:text-secondary-400">Play sound for notifications</p>
                  </div>
                  <Switch checked={false} onChange={() => {}} />
                </div>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="appearance" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Theme</h2>
              <div className="grid grid-cols-3 gap-4">
                {(['light', 'dark', 'system'] as const).map((theme) => (
                  <button
                    key={theme}
                    onClick={() => { /* setTheme(theme) */ }}
                    className={cn(
                      'relative p-4 rounded-xl border-2 transition-all',
                      'hover:border-primary-400 dark:hover:border-primary-500',
                      'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      'bg-white dark:bg-secondary-900'
                    )}
                  >
                    <input type="radio" name="theme" value={theme} className="sr-only" />
                    <div className="text-center">
                      <div className={cn(
                        'w-16 h-16 mx-auto rounded-xl mb-3 flex items-center justify-center',
                        theme === 'light' && 'bg-white border border-secondary-200',
                        theme === 'dark' && 'bg-secondary-900 border border-secondary-700',
                        theme === 'system' && 'bg-gradient-to-br from-white to-secondary-900 border border-secondary-300 dark:border-secondary-600'
                      )}>
                        {theme === 'light' && <Sun className="w-8 h-8 text-yellow-500" />}
                        {theme === 'dark' && <Moon className="w-8 h-8 text-blue-400" />}
                        {theme === 'system' && <Monitor className="w-8 h-8 text-secondary-600" />}
                      </div>
                      <p className="font-medium text-secondary-900 dark:text-white capitalize">{theme}</p>
                      <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-1">
                        {theme === 'light' ? 'Always light' : theme === 'dark' ? 'Always dark' : 'Match system'}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Density</h2>
              <div className="grid grid-cols-3 gap-4">
                {['comfortable', 'compact', 'spacious'].map((density) => (
                  <button key={density} className={cn(
                    'relative p-4 rounded-xl border-2 transition-all',
                    'hover:border-primary-400 dark:hover:border-primary-500',
                    'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                    'bg-white dark:bg-secondary-900'
                  )}>
                    <input type="radio" name="density" value={density} className="sr-only" />
                    <div className="text-center">
                      <div className="w-16 h-16 mx-auto rounded-xl mb-3 bg-secondary-100 dark:bg-secondary-800 flex items-center justify-center">
                        {density === 'comfortable' && <span className="text-2xl">◻ ◻ ◻</span>}
                        {density === 'compact' && <span className="text-sm">◻◻◻</span>}
                        {density === 'spacious' && <span className="text-3xl">◻  ◻  ◻</span>}
                      </div>
                      <p className="font-medium text-secondary-900 dark:text-white capitalize">{density}</p>
                      <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-1">
                        {density === 'comfortable' && 'Default spacing'}
                        {density === 'compact' && 'Tighter spacing'}
                        {density === 'spacious' && 'More breathing room'}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Sidebar</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-secondary-900 dark:text-white">Collapsed by default</p>
                    <p className="text-sm text-secondary-500 dark:text-secondary-400">Start with sidebar collapsed</p>
                  </div>
                  <Switch checked={false} onChange={() => {}} />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-secondary-900 dark:text-white">Show descriptions</p>
                    <p className="text-sm text-secondary-500 dark:text-secondary-400">Show item descriptions in sidebar</p>
                  </div>
                  <Switch checked={true} onChange={() => {}} />
                </div>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="api" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">API Keys</h2>
                <Button onClick={() => {}}>
                  <Key className="w-4 h-4 mr-2" />
                  Create New Key
                </Button>
              </div>
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Key Preview</th>
                      <th>Permissions</th>
                      <th>Last Used</th>
                      <th>Expires</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="font-medium">Production API</td>
                      <td className="font-mono text-sm">rf_live_abc123****xyz789</td>
                      <td><Badge variant="secondary">Full Access</Badge></td>
                      <td className="text-secondary-500">2 hours ago</td>
                      <td className="text-secondary-500">Never</td>
                      <td>
                        <button className="p-2 rounded-lg text-error-600 hover:bg-error-50 dark:hover:bg-error-900/30" aria-label="Revoke">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                    <tr>
                      <td className="font-medium">Development Key</td>
                      <td className="font-mono text-sm">rf_dev_def456****uvw012</td>
                      <td><Badge variant="outline">Read Only</Badge></td>
                      <td className="text-secondary-500">3 days ago</td>
                      <td className="text-secondary-500">30 days</td>
                      <td>
                        <button className="p-2 rounded-lg text-error-600 hover:bg-error-50 dark:hover:bg-error-900/30" aria-label="Revoke">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="integrations" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">External Integrations</h2>
              <p className="text-secondary-600 dark:text-secondary-400">Connect external services to extend RIFT's capabilities.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { name: 'Supabase', description: 'Database & Auth', connected: true, icon: Database },
                  { name: 'Supabase Realtime', description: 'Live subscriptions', connected: true, icon: Zap },
                  { name: 'Lemon Squeezy', description: 'Billing & Subscriptions', connected: false, icon: CreditCard },
                  { name: 'GitHub', description: 'Repository sync', connected: false, icon: Github },
                  { name: 'Slack', description: 'Notifications', connected: false, icon: MessageSquare },
                  { name: 'PagerDuty', description: 'Incident alerts', connected: false, icon: AlertTriangle },
                ].map((integration) => (
                  <div key={integration.name} className="flex items-center justify-between p-4 rounded-lg border border-secondary-200 dark:border-secondary-700">
                    <div className="flex items-center gap-4">
                      <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                        <integration.icon className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                      </div>
                      <div>
                        <p className="font-medium text-secondary-900 dark:text-white">{integration.name}</p>
                        <p className="text-sm text-secondary-500 dark:text-secondary-400">{integration.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant={integration.connected ? 'success' : 'secondary'}>
                        {integration.connected ? 'Connected' : 'Not Connected'}
                      </Badge>
                      <Button variant={integration.connected ? 'ghost' : 'outline'} size="sm">
                        {integration.connected ? 'Disconnect' : 'Connect'}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="data" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Data Export</h2>
              <p className="text-secondary-600 dark:text-secondary-400">Download your data in various formats.</p>
              <div className="flex flex-wrap gap-3">
                <Button variant="outline">
                  <Download className="w-4 h-4 mr-2" />
                  Export Profile (JSON)
                </Button>
                <Button variant="outline">
                  <Download className="w-4 h-4 mr-2" />
                  Export Runs (CSV)
                </Button>
                <Button variant="outline">
                  <Download className="w-4 h-4 mr-2" />
                  Export Experiments (JSON)
                </Button>
                <Button variant="outline">
                  <Download className="w-4 h-4 mr-2" />
                  Export All Data (ZIP)
                </Button>
              </div>
            </div>
          </Card>

          <Card className="border-error-200 dark:border-error-800">
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Delete Account</h2>
                  <p className="text-secondary-600 dark:text-secondary-400">Permanently delete your account and all associated data.</p>
                </div>
                <Button variant="destructive" className="ml-auto">
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete Account
                </Button>
              </div>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}