export default function About({ onBack }) {
  return (
    <main className="about">
      <button className="link" onClick={onBack}>← Back</button>
      <h1>About BruinBuddy</h1>
      <p>
        BruinBuddy is an AI study tutor for a course. It answers from the materials your instructor uploaded and cites
        them, but it is an AI and can make mistakes. Check important details against the original documents.
      </p>
      <h2>How it handles problem sets</h2>
      <p>
        Your instructor sets a rule for each problem set: <em>Graded: hints only</em>, <em>Practice: full help</em>, or{' '}
        <em>Solutions open</em>. The tutor follows that rule and shows it in the chat. For graded sets it gives hints and
        asks about your approach, and it won’t give the answer however the question is phrased.
      </p>
      <h2>Your privacy</h2>
      <p>
        Course staff see aggregate usage (for example how many questions were asked, which materials were cited most,
        and questions the materials didn’t cover, without names). They do not see your individual chats. AI-guided
        assignments are graded work: staff see your score, your progress and that assignment’s conversation. A question you ask in Ask the course
        is private until you, or a course rule, send it to the course staff. Your messages
        and the relevant course text are sent to the AI model provider to generate answers; they are not used to train
        models. The tutor keeps short study notes about what you’re working on in each course so it can pick up where you
        left off.
      </p>
      <h2>Demo course materials</h2>
      <p>
        The demo course uses content from MIT OpenCourseWare, <em>18.05 Introduction to Probability and Statistics</em>,
        Spring 2022, by Jeremy Orloff and Jonathan Bloom, licensed under{' '}
        <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noreferrer">CC BY-NC-SA 4.0</a>.
        Non-commercial use only. Source:{' '}
        <a href="https://ocw.mit.edu/courses/18-05-introduction-to-probability-and-statistics-spring-2022/" target="_blank" rel="noreferrer">MIT OCW</a>.
        Instructors confirm they have the right to use any materials they upload. BruinBuddy is a class project and is not
        affiliated with MIT or UCLA.
      </p>
    </main>
  )
}
