import Duration from 'luxon/src/duration.js'

// We don't have any support for locales in Intl yet, so this just has static formats
export default {
  props: ['value'],
  computed: {
    duration() {
      return Duration.fromISO(this.value).toFormat('hh:mm:ss')
    },
    forHumans() {
      const duration = Duration.fromISO(this.value).shiftTo('hours', 'minutes', 'seconds').toObject()
      let parts = []
      for (let unit in duration) {
        const value = Math.round(duration[unit])
        if (value !== 0) {
          if (value === 1) {
            unit = unit.slice(0, -1)
          }
          parts.push(`${value} ${unit}`)
        }
      }
      return parts.slice(0, 2).join(', ')
    },
  },
}
