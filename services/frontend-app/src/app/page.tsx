/**
 * Kairus Platform - Home Page
 * Main landing page for the application
 */

import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-gray-900">Pulse Platform</h1>
            </div>
            <nav className="flex space-x-8">
              <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
                Dashboard
              </Link>
              <Link href="/analytics" className="text-gray-600 hover:text-gray-900">
                Analytics
              </Link>
              <Link href="/etl" className="text-gray-600 hover:text-gray-900">
                ETL Management
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 sm:text-5xl md:text-6xl">
            Software Engineering
            <span className="text-blue-600"> Intelligence</span>
          </h1>
          <p className="mt-3 max-w-md mx-auto text-base text-gray-500 sm:text-lg md:mt-5 md:text-xl md:max-w-3xl">
            Comprehensive platform for extracting, analyzing, and visualizing software engineering data
            from Jira, GitHub, and other development tools.
          </p>
          <div className="mt-5 max-w-md mx-auto sm:flex sm:justify-center md:mt-8">
            <div className="rounded-md shadow">
              <Link
                href="/dashboard"
                className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 md:py-4 md:text-lg md:px-10"
              >
                Get Started
              </Link>
            </div>
            <div className="mt-3 rounded-md shadow sm:mt-0 sm:ml-3">
              <Link
                href="/docs"
                className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-blue-600 bg-white hover:bg-gray-50 md:py-4 md:text-lg md:px-10"
              >
                Documentation
              </Link>
            </div>
          </div>
        </div>

        {/* Features Section */}
        <div className="mt-20">
          <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {/* ETL Service */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-center h-12 w-12 rounded-md bg-blue-500 text-white mx-auto">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 1.79 4 4 4h8c2.21 0 4-1.79 4-4V7c0-2.21-1.79-4-4-4H8c-2.21 0-4 1.79-4 4z" />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-medium text-gray-900 text-center">ETL Service</h3>
              <p className="mt-2 text-sm text-gray-500 text-center">
                Deep data extraction from Jira including dev_status endpoint to Snowflake Data Warehouse.
              </p>
            </div>

            {/* AI Service */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-center h-12 w-12 rounded-md bg-green-500 text-white mx-auto">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-medium text-gray-900 text-center">AI Analytics</h3>
              <p className="mt-2 text-sm text-gray-500 text-center">
                Machine learning models for predictions, risk analysis, and performance insights.
              </p>
            </div>

            {/* Backend API */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-center h-12 w-12 rounded-md bg-purple-500 text-white mx-auto">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-medium text-gray-900 text-center">Backend API</h3>
              <p className="mt-2 text-sm text-gray-500 text-center">
                Unified API layer aggregating data from ETL and AI services with authentication.
              </p>
            </div>

            {/* Dashboard */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-center h-12 w-12 rounded-md bg-orange-500 text-white mx-auto">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-medium text-gray-900 text-center">Dashboard</h3>
              <p className="mt-2 text-sm text-gray-500 text-center">
                Interactive dashboards for visualizing metrics, trends, and insights.
              </p>
            </div>
          </div>
        </div>

        {/* Status Section */}
        <div className="mt-20 bg-white rounded-lg shadow-md p-8">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">Service Status</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="text-center">
              <div className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                ETL Service
              </div>
              <p className="mt-2 text-sm text-gray-500">Port 8000</p>
            </div>
            <div className="text-center">
              <div className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                AI Service
              </div>
              <p className="mt-2 text-sm text-gray-500">Port 8001</p>
            </div>
            <div className="text-center">
              <div className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                Backend API
              </div>
              <p className="mt-2 text-sm text-gray-500">Port 3000</p>
            </div>
            <div className="text-center">
              <div className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                Frontend
              </div>
              <p className="mt-2 text-sm text-gray-500">Port 3001</p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-gray-500">
            <p>&copy; 2024 Kairus Platform. Built for Software Engineering Intelligence.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
