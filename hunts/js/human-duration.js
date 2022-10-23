import {Duration} from 'luxon'
import humanizeDuration from 'humanize-duration'

// We don't have any support for locales in Intl yet, so this just has static formats
export default {
  props: ['value'],
  computed: {
    duration() {
      return Duration.fromISO(this.value).toFormat('hh:mm:ss')
    },
    forHumans() {
      return humanizeDuration(Duration.fromISO(this.value).toMillis(), { largest: 2, round: true })
    },
  },
}
