import { describe, it, expect } from 'vitest';
import { extractKey, isAuthorized, isKeyRequired, safeEqual } from '../lib/auth';

describe('auth', () => {
  it('Bearer', () => {
    expect(isAuthorized({ authorization: 'Bearer sekret' }, 'sekret')).toBe(true);
    expect(isAuthorized({ authorization: 'bearer   sekret' }, 'sekret')).toBe(true);
  });
  it('x-api-key', () => {
    expect(isAuthorized({ 'x-api-key': 'sekret' }, 'sekret')).toBe(true);
  });
  it('zły lub brakujący klucz', () => {
    expect(isAuthorized({ authorization: 'Bearer zly' }, 'sekret')).toBe(false);
    expect(isAuthorized({ authorization: 'Bearer sekret2' }, 'sekret')).toBe(false);
    expect(isAuthorized({}, 'sekret')).toBe(false);
    expect(isAuthorized({ authorization: 'Basic sekret' }, 'sekret')).toBe(false);
  });
  it('brak klucza w env = otwarte', () => {
    expect(isAuthorized({}, '')).toBe(true);
    expect(isAuthorized({}, undefined)).toBe(true);
    expect(isAuthorized({}, '   ')).toBe(true);
    expect(isKeyRequired('')).toBe(false);
    expect(isKeyRequired('x')).toBe(true);
  });
  it('tablica nagłówków', () => {
    expect(extractKey({ 'x-api-key': ['a', 'b'] })).toBe('a');
  });
  it('safeEqual', () => {
    expect(safeEqual('a', 'a')).toBe(true);
    expect(safeEqual('a', 'aa')).toBe(false);
  });
});
