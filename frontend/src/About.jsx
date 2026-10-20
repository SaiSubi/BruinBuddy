export default function About({ onBack }) {
  return (
    <main className="about">
      <button className="link" onClick={onBack}>← Back</button>
      <h1>About BruinBuddy</h1>
      <p>
        BruinBuddy is a class-project demo of an AI study tutor. It answers from the course materials and cites its
        sources, but it is an AI and can make mistakes. Check important details against the original notes.
      </p>
      <p>
        The tutor will not give solutions to assigned problems. It will give hints and ask about your approach.
      </p>
      <h2>Course materials</h2>
      <p>
        Demo course content is from MIT OpenCourseWare, <em>18.05 Introduction to Probability and Statistics</em>,
        Spring 2022, by Jeremy Orloff and Jonathan Bloom, licensed under{' '}
        <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noreferrer">
          CC BY-NC-SA 4.0
        </a>
        . Non-commercial use only. Source: <a href="https://ocw.mit.edu/courses/18-05-introduction-to-probability-and-statistics-spring-2022/" target="_blank" rel="noreferrer">MIT OCW</a>.
        BruinBuddy is not affiliated with MIT or UCLA.
      </p>
    </main>
  )
}
