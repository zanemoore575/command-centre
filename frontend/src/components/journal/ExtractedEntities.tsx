'use client';

interface Person {
  name: string;
  company?: string;
  role?: string;
}

interface Task {
  id: number;
  description: string;
  priority: string;
  status: string;
}

interface Topic {
  id: number;
  name: string;
  description?: string;
  category?: string;
}

interface Insight {
  id: number;
  description: string;
  category?: string;
}

interface Event {
  id: number;
  description: string;
  event_type?: string;
}

interface Challenge {
  id: number;
  description: string;
  challenge_type?: string;
  severity: string;
}

interface Win {
  id: number;
  description: string;
  category?: string;
}

interface ExtractedEntitiesProps {
  people?: Person[];
  tasks?: Task[];
  topics?: Topic[];
  insights?: Insight[];
  events?: Event[];
  challenges?: Challenge[];
  wins?: Win[];
  isProcessed: boolean;
}

export default function ExtractedEntities({
  people = [],
  tasks = [],
  topics = [],
  insights = [],
  events = [],
  challenges = [],
  wins = [],
  isProcessed
}: ExtractedEntitiesProps) {
  if (!isProcessed) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 mt-6">
        <div className="flex items-center gap-2 mb-2">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-yellow-600"></div>
          <h3 className="text-lg font-semibold text-yellow-900">Processing...</h3>
        </div>
        <p className="text-yellow-800">
          AI is analyzing this entry to extract structured information. Refresh in a moment to see results.
        </p>
      </div>
    );
  }

  const hasSomeEntities =
    people.length > 0 ||
    tasks.length > 0 ||
    topics.length > 0 ||
    insights.length > 0 ||
    events.length > 0 ||
    challenges.length > 0 ||
    wins.length > 0;

  if (!hasSomeEntities) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 mt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">🤖 AI Analysis Complete</h3>
        <p className="text-gray-600">
          No specific entities were identified in this entry.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-8 space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">🤖 AI-Extracted Insights</h2>

      {/* People */}
      {people.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-4 flex items-center gap-2">
            👥 People Mentioned ({people.length})
          </h3>
          <div className="space-y-3">
            {people.map((person, index) => (
              <div key={index} className="bg-white rounded-md p-4 shadow-sm">
                <div className="font-medium text-gray-900">{person.name}</div>
                {(person.company || person.role) && (
                  <div className="text-sm text-gray-600 mt-1">
                    {person.company && person.role && `${person.company} • ${person.role}`}
                    {person.company && !person.role && person.company}
                    {!person.company && person.role && person.role}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Topics/Projects */}
      {topics.length > 0 && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-purple-900 mb-4 flex items-center gap-2">
            📁 Topics & Projects ({topics.length})
          </h3>
          <div className="space-y-3">
            {topics.map((topic) => (
              <div key={topic.id} className="bg-white rounded-md p-4 shadow-sm">
                <div className="font-medium text-gray-900">{topic.name}</div>
                {topic.description && (
                  <p className="text-sm text-gray-600 mt-1">{topic.description}</p>
                )}
                {topic.category && (
                  <span className="text-xs px-2 py-1 bg-purple-100 text-purple-800 rounded-full mt-2 inline-block">
                    {topic.category}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tasks/Actions */}
      {tasks.length > 0 && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-green-900 mb-4 flex items-center gap-2">
            ✅ Tasks & Actions ({tasks.length})
          </h3>
          <div className="space-y-3">
            {tasks.map((task) => (
              <div key={task.id} className="bg-white rounded-md p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <p className="text-gray-900 flex-1">{task.description}</p>
                  <div className="flex gap-2 ml-4">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        task.priority === 'high'
                          ? 'bg-red-100 text-red-800'
                          : task.priority === 'medium'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {task.priority}
                    </span>
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        task.status === 'completed'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {task.status}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Events/Activities */}
      {events.length > 0 && (
        <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-cyan-900 mb-4 flex items-center gap-2">
            📅 Events & Activities ({events.length})
          </h3>
          <div className="space-y-3">
            {events.map((event) => (
              <div key={event.id} className="bg-white rounded-md p-4 shadow-sm">
                <p className="text-gray-900">{event.description}</p>
                {event.event_type && (
                  <span className="text-xs px-2 py-1 bg-cyan-100 text-cyan-800 rounded-full mt-2 inline-block">
                    {event.event_type.replace('_', ' ')}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Insights */}
      {insights.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-indigo-900 mb-4 flex items-center gap-2">
            💡 Insights & Realizations ({insights.length})
          </h3>
          <div className="space-y-3">
            {insights.map((insight) => (
              <div key={insight.id} className="bg-white rounded-md p-4 shadow-sm">
                <p className="text-gray-900">{insight.description}</p>
                {insight.category && (
                  <span className="text-xs px-2 py-1 bg-indigo-100 text-indigo-800 rounded-full mt-2 inline-block">
                    {insight.category}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Challenges */}
      {challenges.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-orange-900 mb-4 flex items-center gap-2">
            ⚠️ Challenges & Blockers ({challenges.length})
          </h3>
          <div className="space-y-3">
            {challenges.map((challenge) => (
              <div key={challenge.id} className="bg-white rounded-md p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="text-gray-900">{challenge.description}</p>
                    {challenge.challenge_type && (
                      <p className="text-sm text-gray-600 mt-1">
                        Type: {challenge.challenge_type.replace('_', ' ')}
                      </p>
                    )}
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded-full ml-4 ${
                      challenge.severity === 'high'
                        ? 'bg-red-100 text-red-800'
                        : challenge.severity === 'medium'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {challenge.severity}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Wins */}
      {wins.length > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-emerald-900 mb-4 flex items-center gap-2">
            🎉 Wins & Successes ({wins.length})
          </h3>
          <div className="space-y-3">
            {wins.map((win) => (
              <div key={win.id} className="bg-white rounded-md p-4 shadow-sm">
                <p className="text-gray-900">{win.description}</p>
                {win.category && (
                  <span className="text-xs px-2 py-1 bg-emerald-100 text-emerald-800 rounded-full mt-2 inline-block">
                    {win.category}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
