<template>
  <van-config-provider :theme-vars="themeVars">
    <router-view />
  </van-config-provider>
</template>

<script setup>
import { ConfigProviderThemeVars } from 'vant'

const themeVars = {
  primaryColor: '#C68B8B',
  primaryLight: '#D4A5A5',
  primaryLighter: '#E8D0D0',
  successColor: '#8BAA8B',
  warningColor: '#D4A574',
  dangerColor: '#C67676',
  tabActiveTextColor: '#C68B8B',
  navBarBackgroundColor: '#FAF6F4',
  navBarTitleTextColor: '#4A3F3F',
  cellBackgroundColor: '#FFFFFF',
  tabBarActiveTextColor: '#C68B8B',
  tabBarBackgroundColor: '#FFFFFF',
  buttonPrimaryBackgroundColor: '#C68B8B',
  buttonPrimaryBorderColor: '#C68B8B'
}
</script>
